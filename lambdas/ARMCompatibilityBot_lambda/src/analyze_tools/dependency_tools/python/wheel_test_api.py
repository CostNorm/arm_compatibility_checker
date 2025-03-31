import requests
import zipfile
import io
import lzma
import json
import logging
from typing import Optional, Dict, Any
from config import GITHUB_TOKEN  # GITHUB_TOKEN을 config.py에서 관리한다고 가정

logger = logging.getLogger(__name__)

# --- GitHub Actions 관련 상수 ---
OWNER = "geoffreyblake"
REPO = "arm64-python-wheel-tester"
WORKFLOW_ID = "wheel-test.yaml"
# 아티팩트 이름은 'results' 또는 'test-results' 등으로 예상, 패턴으로 찾거나 첫 번째 것을 사용
ARTIFACT_NAME_PATTERN = "results"

# --- 간단한 인메모리 캐시 ---
_latest_results_cache: Optional[Dict[str, Any]] = None
_cache_fetched = False


def _get_github_api_headers() -> Dict[str, str]:
    """GitHub API 요청 헤더 생성"""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN이 설정되지 않았습니다.")
    return {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }


def get_latest_wheel_tester_results() -> Optional[Dict[str, Any]]:
    """
    GitHub Actions에서 최신 arm64-python-wheel-tester 성공 실행의
    결과 아티팩트(JSON)를 가져와 파싱합니다.

    Returns:
        파싱된 JSON 데이터 (dict) 또는 실패 시 None. 캐싱 사용.
    """
    global _latest_results_cache, _cache_fetched
    if _cache_fetched:
        logger.info("캐시된 wheel tester 결과 사용.")
        return _latest_results_cache

    logger.info(f"{OWNER}/{REPO} 레포지토리에서 최신 wheel tester 결과 가져오는 중...")
    api_base = f"https://api.github.com/repos/{OWNER}/{REPO}/actions"

    try:
        headers = _get_github_api_headers()

        # 1. 가장 최근의 성공한 워크플로우 실행 찾기
        runs_url = f"{api_base}/workflows/{WORKFLOW_ID}/runs?status=success&per_page=5"  # 최근 5개 확인
        logger.debug(f"워크플로우 실행 목록 가져오기: {runs_url}")
        runs_response = requests.get(runs_url, headers=headers, timeout=15)
        runs_response.raise_for_status()
        runs_data = runs_response.json()

        if (
            not runs_data
            or "workflow_runs" not in runs_data
            or not runs_data["workflow_runs"]
        ):
            logger.warning("성공한 워크플로우 실행을 찾을 수 없습니다.")
            _cache_fetched = True  # 다시 시도하지 않도록 플래그 설정
            return None

        latest_run_id = runs_data["workflow_runs"][0]["id"]
        logger.info(f"최신 성공 실행 ID: {latest_run_id}")

        # 2. 해당 실행의 아티팩트 목록 가져오기
        artifacts_url = f"{api_base}/runs/{latest_run_id}/artifacts"
        logger.debug(f"실행 {latest_run_id}의 아티팩트 가져오기: {artifacts_url}")
        artifacts_response = requests.get(artifacts_url, headers=headers, timeout=15)
        artifacts_response.raise_for_status()
        artifacts_data = artifacts_response.json()

        if (
            not artifacts_data
            or "artifacts" not in artifacts_data
            or not artifacts_data["artifacts"]
        ):
            logger.warning(f"실행 {latest_run_id}에 아티팩트가 없습니다.")
            _cache_fetched = True
            return None

        # 결과 아티팩트 찾기 (이름 패턴 또는 첫 번째)
        target_artifact = None
        for artifact in artifacts_data["artifacts"]:
            if ARTIFACT_NAME_PATTERN in artifact["name"].lower():
                target_artifact = artifact
                break
        if not target_artifact:
            target_artifact = artifacts_data["artifacts"][0]  # fallback

        artifact_id = target_artifact["id"]
        artifact_name = target_artifact["name"]
        logger.info(f"결과 아티팩트 찾음: '{artifact_name}' (ID: {artifact_id})")

        # 3. 아티팩트 다운로드 (zip)
        download_url = f"{api_base}/artifacts/{artifact_id}/zip"
        logger.info(f"아티팩트 다운로드 중: {download_url}")
        download_response = requests.get(
            download_url, headers=headers, allow_redirects=True, timeout=60  # 시간 늘림
        )
        download_response.raise_for_status()
        logger.info("아티팩트 다운로드 완료.")

        # 4. Zip 파일에서 .json.xz 추출 및 파싱
        logger.info("Zip 파일에서 결과 추출 및 파싱 중...")
        with io.BytesIO(download_response.content) as zip_buffer:
            with zipfile.ZipFile(zip_buffer) as zf:
                result_filename = None
                for name in zf.namelist():
                    if name.endswith(".json.xz"):
                        result_filename = name
                        logger.info(f"Zip 내부 결과 파일 찾음: {result_filename}")
                        break

                if not result_filename:
                    logger.error(
                        "Zip 아티팩트 내부에 .json.xz 파일을 찾을 수 없습니다."
                    )
                    _cache_fetched = True
                    return None

                with zf.open(result_filename) as xz_file:
                    # lzma.open은 bytes-like 객체 또는 파일 객체를 받음
                    with lzma.open(xz_file, "rt", encoding="utf-8") as json_file:
                        parsed_results = json.load(json_file)
                        logger.info(f"'{result_filename}' 파싱 성공.")
                        _latest_results_cache = parsed_results  # 캐시 저장
                        _cache_fetched = True
                        return parsed_results

    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API 요청 오류: {e}")
    except zipfile.BadZipFile:
        logger.error("다운로드된 아티팩트가 유효한 Zip 파일이 아닙니다.")
    except lzma.LZMAError as e:
        logger.error(f"XZ 압축 해제 오류: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}")
    except KeyError as e:
        logger.error(f"API 응답에서 예상 키 누락: {e}")
    except ValueError as e:  # GITHUB_TOKEN 누락 시
        logger.error(f"설정 오류: {e}")
    except Exception as e:
        logger.exception(f"결과 가져오기 중 예외 발생: {e}")

    _cache_fetched = True  # 오류 발생 시에도 다시 시도하지 않음
    return None

"""
Python 언어 호환성 체커 구현

이 모듈은 Python 패키지의 ARM 호환성을 확인하고 문제를 해결하는 기능을 제공합니다.

패키지 호환성 해결 순서: function:

1. ARM 휠 가용성 확인(https://pypi.org/) function: check_arm_wheel_availability
   - 네이티브 ARM 휠이 있는 경우 바로 사용

2. ARM64 Python Wheel Tester(https://geoffreyblake.github.io/arm64-python-wheel-tester/) 결과 확인 function: check_arm64_wheel_tester
   - 테스트 통과: 호환성 확인됨
   - 테스트 실패: 대체 패키지 검색
   - 테스트 결과 없음: AWS ARM 환경 컴파일 제안

3. 소스 컴파일 시도 (Case A) function: try_source_compilation
   - 소스 코드를 직접 컴파일하여 ARM 호환성 확인

4. 대체 패키지 검색 (Case C) function: find_alternative_package
   - 호환성 문제가 있는 경우 ARM 지원 대체 패키지 제안 (현재 대체 패키지 없음)

"""

import os
import re
import json
import subprocess
import sys
import tempfile
from bs4 import BeautifulSoup
import requests
import logging
from typing import Dict, Any, Optional

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for PyPI package information to avoid repeated API calls
PYPI_CACHE = {}

build_env = {
    "CFLAGS": "-march=armv8-a -O3",
    "CXXFLAGS": "-march=armv8-a -O3",
    "MAKEFLAGS": "-j4",  # 병렬 빌드 활성화
    "ARCHFLAGS": "-arch arm64",  # macOS/ARM 특화 플래그
}


def check_pypi_package_arm_compatibility(package_name, package_version=None):
    """
    Check if a PyPI package is compatible with ARM64 architecture.
    Uses PyPI API to check for ARM64 wheel availability or universal compatibility.

    Args:
        package_name (str): Name of the package (e.g., "pybloomfiltermmap3" or "numpy>=1.20").
        package_version (str, optional): Specific version to check (e.g., "0.6.0").

    Returns:
        dict: {"compatible": bool or "partial" or "unknown", "reason": str}
    """
    cache_key = f"{package_name}@{package_version}" if package_version else package_name
    if cache_key in PYPI_CACHE:
        return PYPI_CACHE[cache_key]

    try:

        # 패키지 이름 정리
        package_name = package_name.strip().lower()
        clean_name = re.sub(r"[=<>!~].*$", "", package_name)  # 버전 지정자 제거

        # PyPI JSON API 호출
        url = f"https://pypi.org/pypi/{clean_name}/json"
        if package_version:
            url = f"https://pypi.org/pypi/{clean_name}/{package_version}/json"

        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            logger.warning(
                f"Failed to fetch package info for {clean_name}: HTTP {response.status_code}"
            )
            return {
                "compatible": "unknown",
                "reason": f"Package not found or PyPI API error: {response.status_code}",
            }

        data = response.json()

        # 특정 버전 확인 또는 최신 버전 사용
        if package_version:
            if package_version not in data["releases"]:
                return {
                    "compatible": "unknown",
                    "reason": f"Version {package_version} not found",
                }
            releases = data["releases"][package_version]
        else:
            # 최신 버전 사용 (urls 필드가 현재 버전의 배포 파일 정보를 담고 있음)
            releases = data["urls"]

        # 플랫폼 호환성 확인 개선
        arm_wheels = []
        universal_wheels = []
        sdist_files = []

        for release in releases:
            filename = release.get("filename", "")
            packagetype = release.get("packagetype", "")

            # 휠 파일 확인
            if packagetype == "bdist_wheel":
                # 파일명에서 플랫폼 태그 추출
                platform_tag = (
                    filename.rsplit("-", 1)[1].split(".whl")[0]
                    if ".whl" in filename
                    else ""
                )

                # ARM 호환 휠 확인
                if any(
                    arm_id in platform_tag.lower()
                    for arm_id in ["aarch64", "arm64", "armv8", "armv7l"]
                ):
                    arm_wheels.append(filename)
                # 범용 휠 확인
                elif platform_tag == "any" or "none-any" in platform_tag:
                    universal_wheels.append(filename)

            # 소스 배포판 확인
            elif packagetype == "sdist":
                sdist_files.append(filename)

        # requires_python 필드 확인
        requires_python = data["info"].get("requires_python", "")

        # 플랫폼 필드 확인 (null이면 플랫폼 독립적)
        platform = data["info"].get("platform")
        is_platform_independent = platform is None or platform == ""

        # 결과 결정
        if arm_wheels:
            result = {
                "compatible": True,
                "reason": f"ARM-specific wheels available: {', '.join(arm_wheels)}",
            }
        elif universal_wheels:
            result = {
                "compatible": True,
                "reason": f"Universal wheels available: {', '.join(universal_wheels)}",
            }
        elif sdist_files and is_platform_independent:
            result = {
                "compatible": True,
                "reason": f"Platform-independent source distribution available: {', '.join(sdist_files)}",
            }
        elif sdist_files:
            # 확장 모듈이 있는지 확인하기 위한 분류자 검사
            classifiers = data["info"].get("classifiers", [])
            has_c_extension = any("Programming Language :: C" in c for c in classifiers)
            has_cython = any("Programming Language :: Cython" in c for c in classifiers)

            if has_c_extension or has_cython:
                result = {
                    "compatible": "partial",
                    "reason": "Source distribution with C/Cython extensions may require compilation",
                }
            else:
                result = {
                    "compatible": True,
                    "reason": "Pure Python source distribution, likely compatible",
                }
        else:
            result = {
                "compatible": False,
                "reason": "No compatible wheels or source distribution available",
            }

        # 패키지가 yanked(철회)되었는지 확인
        if data["info"].get("yanked", False):
            yanked_reason = data["info"].get("yanked_reason", "No reason provided")
            result["warning"] = f"Package version has been yanked: {yanked_reason}"

        # 캐싱
        PYPI_CACHE[cache_key] = result
        return result

    except Exception as e:
        logger.error(f"Error checking {package_name}: {str(e)}")
        return {
            "compatible": "unknown",
            "reason": f"Error checking compatibility: {str(e)}",
        }


def check_arm64_wheel_tester(
    package_name: str, version: Optional[str] = None
) -> Dict[str, Any]:
    """
    ARM64 Python Wheel Tester 웹사이트에서 패키지 호환성 결과 확인

    Args:
        package_name: 패키지 이름
        version: 패키지 버전 (선택 사항)

    Returns:
        테스트 결과 정보
    """
    logger.info(f"ARM64 Wheel Tester 결과 확인 중: {package_name}")

    try:
        # ARM64 Python Wheel Tester 웹사이트에서 데이터 가져오기
        url = "https://geoffreyblake.github.io/arm64-python-wheel-tester/"
        response = requests.get(url)
        response.raise_for_status()

        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(response.text, "html.parser")

        # 패키지 이름 정규화 (대소문자, '-', '_' 차이 처리)
        normalized_name = package_name.lower().replace("-", "_")

        # 테스트 결과 테이블 찾기
        package_found = False
        test_result = "unknown"

        # 테이블 행 순회
        for row in soup.select("table tr"):
            cells = row.select("td")
            if not cells or len(cells) < 2:
                continue

            # 첫 번째 셀에서 패키지 이름 추출
            row_package = cells[0].text.strip().lower().replace("-", "_")

            # 패키지 이름 일치 확인
            if row_package == normalized_name:
                package_found = True

                # 버전 확인 (버전이 지정된 경우)
                if version:
                    row_version = cells[1].text.strip() if len(cells) > 1 else ""
                    if row_version != version:
                        continue

                # 결과 셀에서 테스트 결과 추출
                result_cell = cells[-1].text.strip().lower() if len(cells) > 2 else ""

                if "pass" in result_cell:
                    test_result = "pass"
                    break
                elif "fail" in result_cell:
                    test_result = "fail"
                    break

        if package_found:
            if test_result == "pass":
                return {
                    "name": package_name,
                    "version_spec": version,
                    "compatible": True,
                    "reason": "ARM64 Python Wheel Tester에서 테스트 통과",
                    "source": "arm64_wheel_tester",
                }
            elif test_result == "fail":
                return {
                    "name": package_name,
                    "version_spec": version,
                    "compatible": False,
                    "reason": "ARM64 Python Wheel Tester에서 테스트 실패",
                    "source": "arm64_wheel_tester",
                }

        # 패키지를 찾지 못한 경우
        return {
            "name": package_name,
            "version_spec": version,
            "compatible": "unknown",
            "reason": "ARM64 Python Wheel Tester에서 패키지 정보 없음",
            "source": "arm64_wheel_tester",
        }

    except Exception as e:
        logger.error(f"ARM64 Wheel Tester 확인 중 오류 발생: {str(e)}")
        return {
            "name": package_name,
            "version_spec": version,
            "compatible": "unknown",
            "reason": f"ARM64 Wheel Tester 확인 중 오류: {str(e)}",
            "source": "arm64_wheel_tester",
        }


def try_source_compilation(
    package_name: str, version: Optional[str] = None
) -> Dict[str, Any]:
    """
    소스 코드에서 컴파일 시도 (Case A 확인)

    Args:
        package_name: 패키지 이름
        version: 패키지 버전 (선택 사항)

    Returns:
        컴파일 결과 정보
    """
    package_spec = f"{package_name}" if not version else f"{package_name}=={version}"
    logger.info(f"소스 컴파일 시도 중: {package_spec}")

    # 임시 가상 환경 생성
    venv_dir = os.path.join(
        tempfile.mkdtemp(prefix="arm_compat_"), f"{package_name}_venv"
    )

    try:
        # 가상 환경 생성
        subprocess.run(
            [sys.executable, "-m", "venv", venv_dir],
            check=True,
            capture_output=True,
            text=True,
        )

        # 가상 환경의 pip 경로
        pip_path = (
            os.path.join(venv_dir, "bin", "pip")
            if os.name != "nt"
            else os.path.join(venv_dir, "Scripts", "pip.exe")
        )

        # 빌드 의존성 설치
        subprocess.run(
            [pip_path, "install", "--upgrade", "pip", "wheel", "setuptools"],
            check=True,
            capture_output=True,
            text=True,
            env=build_env,
        )

        # 소스에서 설치 시도
        result = subprocess.run(
            [pip_path, "install", "--no-binary", ":all:", package_spec],
            capture_output=True,
            text=True,
            env=build_env,
        )

        # 설치 성공 여부 확인
        if result.returncode == 0:
            return {
                "name": package_name,
                "version_spec": version,
                "compatible": True,
                "case": "A",
                "reason": "소스 컴파일 성공",
                "build_output": result.stdout,
                "build_error": None,
            }
        else:
            return {
                "name": package_name,
                "version_spec": version,
                "compatible": False,
                "case": None,
                "reason": "소스 컴파일 실패",
                "build_output": result.stdout,
                "build_error": result.stderr,
            }

    except Exception as e:
        logger.error(f"소스 컴파일 중 오류 발생: {str(e)}")
        return {
            "name": package_name,
            "version_spec": version,
            "compatible": False,
            "case": None,
            "reason": f"소스 컴파일 중 오류 발생: {str(e)}",
            "build_output": None,
            "build_error": str(e),
        }


def parse_package_json(content):
    """Parse package.json file and check ARM compatibility of Node.js packages."""
    results = []

    try:
        package_data = json.loads(content)
        dependencies = package_data.get("dependencies", {})
        dev_dependencies = package_data.get("devDependencies", {})

        # Combine all dependencies
        all_deps = {}
        all_deps.update(dependencies)
        all_deps.update(dev_dependencies)

        # Known Node.js packages with potential ARM64 issues
        problematic_packages = [
            "node-sass",
            "sharp",
            "canvas",
            "grpc",
            "electron",
            "node-gyp",
            "robotjs",
            "sqlite3",
            "bcrypt",
        ]

        for pkg, ver in all_deps.items():
            # Simple heuristic for checking Node.js package compatibility
            is_problematic = any(prob in pkg.lower() for prob in problematic_packages)

            if is_problematic:
                compatibility = {
                    "dependency": f"{pkg}@{ver}",
                    "name": pkg,
                    "version": ver,
                    "compatible": "partial",
                    "reason": "Package may have native dependencies that need to be rebuilt for ARM64",
                }
            else:
                compatibility = {
                    "dependency": f"{pkg}@{ver}",
                    "name": pkg,
                    "version": ver,
                    "compatible": True,
                    "reason": "Likely compatible (pure JavaScript or supports ARM64)",
                }

            results.append(compatibility)

    except json.JSONDecodeError:
        results.append(
            {
                "dependency": "Invalid JSON",
                "compatible": "unknown",
                "reason": "Invalid JSON format",
            }
        )

    return results


# 예시 사용
if __name__ == "__main__":
    # pybloomfiltermmap3 최신 버전 확인
    result = check_pypi_package_arm_compatibility("rbloom")
    print(result)

    # 특정 버전 확인
    result = check_pypi_package_arm_compatibility("pybloomfiltermmap3", "0.6.0")
    print(result)

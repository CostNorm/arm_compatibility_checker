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

3. 소스 컴파일 시도 (Case A) function: try_source_compilation - 제거됨
   - 소스 코드를 직접 컴파일하여 ARM 호환성 확인

4. 대체 패키지 검색 (Case C) function: find_alternative_package - 미구현
   - 호환성 문제가 있는 경우 ARM 지원 대체 패키지 제안 (현재 대체 패키지 없음)

"""

import os
import json
import subprocess
import sys
import tempfile
import logging
from typing import Dict, Any, Optional, Union

# 경로 수정: wheel_test_api -> .wheel_test_api (상대 경로)
from .wheel_test_api import get_latest_wheel_tester_results

# 경로 수정: pypi_api -> .pypi_api (상대 경로)
from .pypi_api import check_pypi_package_arm_compatibility

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_python_package_compatibility(
    package_name: str,
    version_spec: Optional[str] = None,
    original_line: Optional[str] = None,
    direct: bool = True,
    parent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    패키지의 ARM 호환성을 검사합니다. PyPI API와 wheel tester 결과를 사용합니다.
    PyPI 결과에 warning이 있으면 reason에 포함시킵니다.
    """
    # 패키지 이름 정리 (정규화는 pypi_api에서 처리)
    clean_name = package_name.lower().replace(
        "_", "-"
    )  # API 호출 전에 정규화된 이름 필요
    debug_info = {
        "pypi_check": None,
        "wheel_tester_check": None,
    }
    final_compatibility: Union[bool, str] = "unknown"
    final_reason = "Compatibility status could not be determined."
    pypi_warning = None  # PyPI 경고를 저장할 변수

    # --- 1단계: PyPI API 확인 ---
    try:
        # API 호출 시 정제되지 않은 package_name과 version_spec 전달
        pypi_result = check_pypi_package_arm_compatibility(package_name, version_spec)
        debug_info["pypi_check"] = pypi_result
        logger.info(f"[{package_name}] PyPI Check: {pypi_result}")

        # 경고 저장
        pypi_warning = pypi_result.get("warning")

        if pypi_result.get("compatible") is True:
            final_compatibility = True
            final_reason = pypi_result.get("reason", "Compatible according to PyPI.")
            # 여기서 바로 반환하지 않고, wheel tester 결과도 확인하도록 변경
        elif pypi_result.get("compatible") is False:
            final_compatibility = False
            final_reason = pypi_result.get("reason", "Incompatible according to PyPI.")
        elif pypi_result.get("compatible") == "partial":
            final_compatibility = "partial"
            final_reason = pypi_result.get(
                "reason", "Partially compatible or requires build (PyPI)."
            )
        else:  # unknown
            final_compatibility = "unknown"
            final_reason = pypi_result.get("reason", "Compatibility unknown (PyPI).")

    except Exception as e:
        logger.error(f"[{package_name}] PyPI check failed: {e}")
        debug_info["pypi_check"] = {"error": str(e)}
        # PyPI 실패 시에도 wheel tester는 시도

    # --- 2단계: Arm64 Wheel Tester 결과 확인 ---
    # Wheel Tester는 정규화된 이름 사용
    normalized_name_for_tester = clean_name  # 이미 위에서 정규화된 이름 사용
    wheel_tester_results_data = get_latest_wheel_tester_results()
    if wheel_tester_results_data:
        if normalized_name_for_tester in wheel_tester_results_data:
            package_test_info = wheel_tester_results_data[normalized_name_for_tester]
            debug_info["wheel_tester_check"] = {
                "status": "found",
                "tests": list(package_test_info.keys()),
            }
            logger.info(
                f"[{normalized_name_for_tester}] Found in Wheel Tester results."
            )

            passed_on_recent_ubuntu = False
            failed_tests = []
            build_required_somewhere = False

            # 최신 Ubuntu 버전부터 확인 (noble -> jammy -> focal)
            for test_env in ["noble", "jammy", "focal"]:
                if test_env in package_test_info:
                    test_result = package_test_info[test_env]
                    if test_result.get("test-passed") is True:
                        passed_on_recent_ubuntu = True
                        # Wheel tester 통과 시, PyPI 결과가 어떻든 compatible로 간주하고 이유 업데이트
                        final_compatibility = True
                        final_reason = f"Passed on {test_env} in Wheel Tester."
                        if test_result.get("build-required") is True:
                            final_reason += " (Build was required)."
                        # 통과하면 더 이상 다른 환경 체크 불필요
                        break
                    else:
                        # 실패한 테스트 기록 (가장 최근 실패를 우선)
                        if not failed_tests:
                            failed_tests.append(test_env)
                    if test_result.get("build-required") is True:
                        build_required_somewhere = True

            # 만약 모든 최신 환경에서 실패했다면
            if not passed_on_recent_ubuntu and failed_tests:
                failed_env = failed_tests[0]  # 가장 최근 실패 환경
                # PyPI 결과가 True나 partial이 아니었다면, Wheel Tester 실패를 이유로 업데이트
                if final_compatibility not in [True, "partial"]:
                    final_compatibility = False
                    final_reason = f"Failed on {failed_env} in Wheel Tester."
                # PyPI 결과가 partial 이었다면, 실패 정보를 추가
                elif final_compatibility == "partial":
                    final_reason += (
                        f" Additionally, failed on {failed_env} in Wheel Tester."
                    )
                # PyPI 결과가 False 였다면, 실패 정보를 추가
                elif final_compatibility is False:
                    final_reason += f" Also failed on {failed_env} in Wheel Tester."

            # 만약 Wheel Tester에서 통과했지만, PyPI에서 빌드 필요했다는 정보가 있었다면?
            # -> Wheel Tester 통과를 더 우선시하므로 final_reason은 이미 업데이트됨.

        else:
            logger.info(
                f"[{normalized_name_for_tester}] Not found in Wheel Tester results."
            )
            debug_info["wheel_tester_check"] = {"status": "not_found"}
            # Wheel Tester 결과 없으면 PyPI 결과가 최종
    else:
        logger.warning(
            f"[{normalized_name_for_tester}] Could not fetch Wheel Tester results."
        )
        debug_info["wheel_tester_check"] = {"status": "fetch_error"}
        # Wheel Tester 결과 없으면 PyPI 결과가 최종

    # --- 최종 결과 정리 ---
    # 소스 컴파일이 필요할 수 있다는 정보 추가 (최종 결과가 partial일 때)
    if final_compatibility == "partial":
        final_reason = (
            final_reason.rstrip(".")
            + ". Source compilation might be required on ARM64."
        )
    # 최종 결과가 unknown일 때 메시지 정리
    elif final_compatibility == "unknown":
        final_reason = f"Could not determine compatibility from PyPI or Wheel Tester ({final_reason}). Manual check recommended."

    # ***** PyPI 경고(Yanked 등)를 최종 reason에 추가 *****
    if pypi_warning:
        final_reason = f"{final_reason.rstrip('.')} (Warning: {pypi_warning})"

    return {
        "dependency": original_line
        or package_name,  # Use original name/line for display
        "name": package_name,  # Keep original name
        "version_spec": version_spec,
        "compatible": final_compatibility,
        "reason": final_reason,  # 최종적으로 경고가 포함될 수 있는 reason
        "direct": direct,
        "parent": parent,
        "debug_info": debug_info,
    }

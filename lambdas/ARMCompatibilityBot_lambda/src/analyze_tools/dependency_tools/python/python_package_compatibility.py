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
import json
import subprocess
import sys
import tempfile
import logging
from typing import Dict, Any, Optional, Union
from .wheel_test_api import get_latest_wheel_tester_results
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
    """
    clean_name = package_name.lower().replace("-", "_")  # 패키지 이름 정리
    debug_info = {
        "pypi_check": None,
        "wheel_tester_check": None,
    }
    final_compatibility: Union[bool, str] = "unknown"
    final_reason = "Compatibility status could not be determined."

    # --- 1단계: PyPI API 확인 ---
    try:
        pypi_result = check_pypi_package_arm_compatibility(clean_name, version_spec)
        debug_info["pypi_check"] = pypi_result
        logger.info(f"[{clean_name}] PyPI Check: {pypi_result}")

        if pypi_result.get("compatible") is True:
            final_compatibility = True
            final_reason = pypi_result.get("reason", "Compatible according to PyPI.")
            return {
                "dependency": original_line or clean_name,
                "name": clean_name,
                "version_spec": version_spec,
                "compatible": final_compatibility,
                "reason": final_reason,
                "direct": direct,
                "parent": parent,
                "debug_info": debug_info,
            }
        elif pypi_result.get("compatible") is False:
            final_compatibility = False
            final_reason = pypi_result.get("reason", "Incompatible according to PyPI.")
        elif pypi_result.get("compatible") == "partial":
            final_compatibility = "partial"
            final_reason = pypi_result.get(
                "reason", "Partially compatible or requires build (PyPI)."
            )
        else:
            final_compatibility = "unknown"
            final_reason = pypi_result.get("reason", "Compatibility unknown (PyPI).")

    except Exception as e:
        logger.error(f"[{clean_name}] PyPI check failed: {e}")
        debug_info["pypi_check"] = {"error": str(e)}

    # --- 2단계: Arm64 Wheel Tester 결과 확인 ---
    wheel_tester_results_data = get_latest_wheel_tester_results()
    if wheel_tester_results_data:
        if clean_name in wheel_tester_results_data:
            package_test_info = wheel_tester_results_data[clean_name]
            debug_info["wheel_tester_check"] = {
                "status": "found",
                "tests": list(package_test_info.keys()),
            }
            logger.info(f"[{clean_name}] Found in Wheel Tester results.")

            passed_on_recent_ubuntu = False
            failed_tests = []
            build_required_somewhere = False

            for test_env in ["noble", "jammy", "focal"]:
                if test_env in package_test_info:
                    test_result = package_test_info[test_env]
                    if test_result.get("test-passed") is True:
                        passed_on_recent_ubuntu = True
                        final_reason = f"Passed on {test_env} in Wheel Tester."
                        break
                    else:
                        failed_tests.append(test_env)
                    if test_result.get("build-required") is True:
                        build_required_somewhere = True

            if passed_on_recent_ubuntu:
                final_compatibility = True
                if build_required_somewhere:
                    final_reason += (
                        " (Note: build might be required on some platforms)."
                    )
            elif failed_tests:
                if final_compatibility in ["unknown", "partial"]:
                    final_compatibility = False
                    final_reason = f"Failed on {', '.join(failed_tests)} in Wheel Tester. {pypi_result.get('reason', '')}"
                elif final_compatibility is False:
                    final_reason += (
                        f" Also failed on {', '.join(failed_tests)} in Wheel Tester."
                    )
        else:
            logger.info(f"[{clean_name}] Not found in Wheel Tester results.")
            debug_info["wheel_tester_check"] = {"status": "not_found"}
    else:
        logger.warning(f"[{clean_name}] Could not fetch Wheel Tester results.")
        debug_info["wheel_tester_check"] = {"status": "fetch_error"}

    # 3. 소스 컴파일 시도 - 제거!
    # source_compilation_result = try_source_compilation(package_name, version_spec)
    # debug_info["source_compilation"] = source_compilation_result
    # if source_compilation_result.get("compatible") == True:
    #     # This part is removed
    #     pass

    # --- 최종 결과 정리 ---
    # 소스 컴파일이 필요할 수 있다는 정보 추가 (PyPI가 partial이거나, 둘 다 unknown일 때)
    if final_compatibility == "partial":
        final_reason = (
            final_reason.rstrip(".")
            + ". Source compilation might be required on ARM64."
        )
    elif final_compatibility == "unknown":
        final_reason = f"Could not determine compatibility from PyPI or Wheel Tester ({final_reason}). Manual check recommended."

    return {
        "dependency": original_line or clean_name,
        "name": clean_name,
        "version_spec": version_spec,
        "compatible": final_compatibility,
        "reason": final_reason,
        "direct": direct,
        "parent": parent,
        "debug_info": debug_info,
    }

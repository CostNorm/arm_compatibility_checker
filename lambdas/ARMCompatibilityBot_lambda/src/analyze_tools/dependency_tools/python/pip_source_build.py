import os
import json
import subprocess
import sys
import tempfile
import logging
from typing import Dict, Any, Optional, Union
from .apis.wheel_test_api import get_latest_wheel_tester_results
from .apis.pypi_api import check_pypi_package_arm_compatibility

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


build_env = {
    "CFLAGS": "-march=armv8-a -O3",
    "CXXFLAGS": "-march=armv8-a -O3",
    "MAKEFLAGS": "-j4",  # 병렬 빌드 활성화
    "ARCHFLAGS": "-arch arm64",  # macOS/ARM 특화 플래그
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


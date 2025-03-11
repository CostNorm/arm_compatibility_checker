import re
import json
import requests
from packaging import version
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for PyPI package information to avoid repeated API calls
PYPI_CACHE = {}


import re
import requests
import logging

logger = logging.getLogger(__name__)
PYPI_CACHE = {}  # 캐시 초기화


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
                    for arm_id in ["aarch64", "arm64", "armv7"]
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


# 예시 사용
if __name__ == "__main__":
    # pybloomfiltermmap3 최신 버전 확인
    result = check_pypi_package_arm_compatibility("pybloomfiltermmap3")
    print(result)

    # 특정 버전 확인
    result = check_pypi_package_arm_compatibility("pybloomfiltermmap3", "0.6.0")
    print(result)


def parse_requirements_txt(content):
    """Parse requirements.txt file and check ARM compatibility of each package."""
    results = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Parse package name and version
        match = re.match(r"^([A-Za-z0-9_.-]+)([<>=!~].+)?$", line)
        if not match:
            continue

        package_name = match.group(1)
        version_spec = match.group(2)

        # Check compatibility
        compatibility = check_pypi_package_arm_compatibility(package_name)
        results.append(
            {
                "dependency": line,
                "name": package_name,
                "version_spec": version_spec,
                "compatible": compatibility.get("compatible"),
                "reason": compatibility.get("reason"),
            }
        )

    return results


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


def analyze_dependency_compatibility(dependency_analysis):
    """
    Analyze dependencies for ARM compatibility
    This function now delegates to the enhanced analyzer
    """
    # Import here to avoid circular imports
    from analyze_tools.enhanced_dependency_analyzer import (
        analyze_enhanced_dependency_compatibility,
    )

    # Forward to the enhanced analyzer
    return analyze_enhanced_dependency_compatibility(dependency_analysis)

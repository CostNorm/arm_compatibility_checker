import re
import subprocess
import tempfile
import logging
from typing import Dict, List, Any
import os
import sys

sys.path.append(os.path.dirname("/Users/woohyeok/development/2025/alpha/"))

# Import the package compatibility checker
from analyze_tools.dependency_tools.package_compatibility import (
    check_arm64_wheel_tester,
    check_pypi_package_arm_compatibility,
    try_source_compilation,
)

# Import the JavaScript compatibility checker
from analyze_tools.dependency_tools.js_compatibility import analyze_package_json

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for dependency trees to avoid repeated pipgrip calls
DEPENDENCY_TREE_CACHE = {}


def get_dependency_tree(requirements_content: str) -> Dict[str, List[str]]:
    """
    Use pipgrip to extract the full dependency tree from requirements content.

    Args:
        requirements_content (str): Content of requirements.txt file

    Returns:
        Dict[str, List[str]]: Dictionary mapping package names to their dependencies
    """
    # Create a hash of the requirements content to use as cache key
    cache_key = hash(requirements_content)

    # Check if we have already processed this requirements file
    if cache_key in DEPENDENCY_TREE_CACHE:
        logger.info("Using cached dependency tree")
        return DEPENDENCY_TREE_CACHE[cache_key]

    # Create a temporary requirements file
    fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="requirements_")
    try:
        with os.fdopen(fd, "w") as tmp:
            tmp.write(requirements_content)

        logger.info(f"Running pipgrip to analyze dependencies from {temp_path}")

        # Run pipgrip to get the dependency tree
        cmd = ["pipgrip", "--tree", "-r", temp_path]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning(f"pipgrip failed: {result.stderr}")
            return {}

        # Parse the tree output
        tree_output = result.stdout
        dependency_tree = parse_pipgrip_tree(tree_output)

        # Cache the result
        DEPENDENCY_TREE_CACHE[cache_key] = dependency_tree

        return dependency_tree

    except Exception as e:
        logger.error(f"Error analyzing dependencies with pipgrip: {str(e)}")
        return {}

    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def parse_pipgrip_tree(tree_output: str) -> Dict[str, List[str]]:
    """
    Parse the output of pipgrip --tree into a structured dependency tree.

    Args:
        tree_output (str): Output from pipgrip --tree command

    Returns:
        Dict[str, List[str]]: Dictionary mapping package names to their dependencies
    """
    dependency_tree = {}
    current_package = None
    package_pattern = re.compile(r"^(\w[\w.-]+).*$")
    dependency_pattern = re.compile(r"^\s+[└├]── (\w[\w.-]+).*$")

    for line in tree_output.splitlines():
        # Match a top-level package
        package_match = package_pattern.match(line)
        if package_match and not line.startswith(" "):
            current_package = clean_package_name(package_match.group(1))
            dependency_tree[current_package] = []
            continue

        # Match a dependency
        if current_package:
            dependency_match = dependency_pattern.match(line)
            if dependency_match:
                dependency = clean_package_name(dependency_match.group(1))
                dependency_tree[current_package].append(dependency)

                # Also ensure the dependency itself is in the tree
                if dependency not in dependency_tree:
                    dependency_tree[dependency] = []

    return dependency_tree


def clean_package_name(name: str) -> str:
    """Clean package name by removing version specifiers."""
    return re.sub(r"[=<>!~].*$", "", name.strip().lower())


def analyze_requirements_with_pipgrip(content: str) -> List[Dict[str, Any]]:
    """
    Analyze a requirements.txt file using pipgrip to find all dependencies
    and check ARM64 compatibility for each.

    Args:
        content (str): Content of requirements.txt file

    Returns:
        List[Dict[str, Any]]: List of dependency compatibility information
    """
    results = []

    # Get direct dependencies first
    direct_dependencies = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Parse package name and version
        match = re.match(r"^([A-Za-z0-9_.-]+)([<>=!~].+)?$", line)
        if match:
            package_name = match.group(1)
            version_spec = match.group(2) if len(match.groups()) > 1 else None
            direct_dependencies.append((package_name, version_spec, line))

    # Get full dependency tree using pipgrip
    try:
        dependency_tree = get_dependency_tree(content)

        # Process direct dependencies first
        for package_name, version_spec, original_line in direct_dependencies:
            clean_name = clean_package_name(package_name)

            # Check compatibility
            compatibility_result = check_package_compatibility(
                package_name, version_spec, original_line, direct=True
            )
            results.append(compatibility_result)

            # Now process transitive dependencies
            if clean_name in dependency_tree:
                for transitive_dep in dependency_tree[clean_name]:
                    # Skip if already in results
                    if not any(
                        r["name"].lower() == transitive_dep.lower() for r in results
                    ):
                        compatibility_result = check_package_compatibility(
                            transitive_dep,
                            None,
                            transitive_dep,
                            direct=False,
                            parent=clean_name,
                        )
                        results.append(compatibility_result)

        # Look for any remaining dependencies in the tree that weren't processed
        for pkg, deps in dependency_tree.items():
            if not any(r["name"].lower() == pkg.lower() for r in results):
                compatibility_result = check_package_compatibility(
                    pkg, None, pkg, direct=False, parent=None
                )
                results.append(compatibility_result)

    except Exception as e:
        logger.error(f"Error in dependency resolution: {str(e)}")
        # Fallback: just analyze direct dependencies if pipgrip fails
        if not results:
            for package_name, version_spec, original_line in direct_dependencies:
                compatibility = check_pypi_package_arm_compatibility(package_name)

                results.append(
                    {
                        "dependency": original_line,
                        "name": package_name,
                        "version_spec": version_spec,
                        "compatible": compatibility.get("compatible"),
                        "reason": compatibility.get("reason"),
                        "direct": True,
                    }
                )

    return results


def check_package_compatibility(
    package_name, version_spec=None, original_line=None, direct=True, parent=None
):
    """
    패키지의 ARM 호환성을 검사하는 함수입니다.

    Args:
        package_name (str): 패키지 이름
        version_spec (str, optional): 버전 스펙
        original_line (str, optional): 원본 의존성 라인
        direct (bool): 직접 의존성 여부
        parent (str, optional): 부모 패키지 이름

    Returns:
        dict: 호환성 검사 결과
    """
    debug_info = {
        "pypi_check": None,
        "wheel_tester_check": None,
        "source_compilation": None,
    }

    # 1. ARM 휠 가용성 확인
    compatibility = check_pypi_package_arm_compatibility(package_name)
    debug_info["pypi_check"] = compatibility
    if compatibility.get("compatible") == True:
        return {
            "dependency": original_line or package_name,
            "name": package_name,
            "version_spec": version_spec,
            "compatible": compatibility.get("compatible"),
            "reason": compatibility.get("reason"),
            "direct": direct,
            "parent": parent,
            "debug_info": debug_info,
        }

    # 2. ARM64 Python Wheel Tester 결과 확인
    compatibility = check_arm64_wheel_tester(package_name, version_spec)
    debug_info["wheel_tester_check"] = compatibility
    if compatibility.get("compatible") == True:
        return {
            "dependency": original_line or package_name,
            "name": package_name,
            "version_spec": version_spec,
            "compatible": compatibility.get("compatible"),
            "reason": compatibility.get("reason"),
            "direct": direct,
            "parent": parent,
            "debug_info": debug_info,
        }

    # 3. 소스 컴파일 시도
    compatibility = try_source_compilation(package_name, version_spec)
    debug_info["source_compilation"] = compatibility
    if compatibility.get("compatible") == True:
        return {
            "dependency": original_line or package_name,
            "name": package_name,
            "version_spec": version_spec,
            "compatible": compatibility.get("compatible"),
            "reason": compatibility.get("reason"),
            "direct": direct,
            "parent": parent,
            "debug_info": debug_info,
        }

    # 모든 검사가 실패한 경우
    detailed_reason = f"""
    호환성 검사 실패 상세 정보:
    1. PyPI ARM 휠 검사: {debug_info['pypi_check'].get('reason', '정보 없음')}
    2. ARM64 Wheel Tester: {debug_info['wheel_tester_check'].get('reason', '정보 없음')}
    3. 소스 컴파일: {debug_info['source_compilation'].get('reason', '정보 없음')}
    """

    return {
        "dependency": original_line or package_name,
        "name": package_name,
        "version_spec": version_spec,
        "compatible": compatibility.get("compatible", False),
        "reason": detailed_reason,
        "direct": direct,
        "parent": parent,
        "debug_info": debug_info,
    }


def analyze_dependency_compatibility(dependency_analysis):
    """
    Analyze dependencies for ARM compatibility.
    Uses pipgrip for transitive dependency analysis.
    """
    dependency_results = []
    recommendations = []
    reasoning = []

    # Problematic packages for Python
    problematic_python_packages = ["tensorflow<2", "torch<1.9", "nvidia-", "cuda"]

    for dep_analysis in dependency_analysis:
        file_path = dep_analysis.get("file", "unknown")
        file_name = file_path.split("/")[-1]

        if file_name == "requirements.txt":
            # Get the file content and parse it properly
            content = dep_analysis.get("content", "")
            if not content and dep_analysis.get("analysis", {}).get("dependencies"):
                content = "\n".join(
                    dep_analysis.get("analysis", {}).get("dependencies", [])
                )

            # Use enhanced analysis with pipgrip
            packages = analyze_requirements_with_pipgrip(content)

            # Track incompatible direct dependencies for better recommendations
            direct_incompatible = []

            for package in packages:
                package["file"] = file_path
                dependency_results.append(package)

                # Generate appropriate recommendations based on compatibility
                if package.get("compatible") is False:
                    package_info = f"{package['name']}{package.get('version_spec', '')}"

                    if package.get("direct", True):
                        reason = f"Python package {package_info} is not compatible with ARM64: {package.get('reason')}"
                        direct_incompatible.append(package["name"])
                        recommendations.append(
                            f"Replace {package_info} with an ARM64 compatible alternative in {file_path}"
                        )
                    else:
                        parent = package.get("parent", "unknown parent")
                        reason = f"Transitive dependency {package_info} (required by {parent}) is not compatible with ARM64: {package.get('reason')}"
                        if parent not in direct_incompatible:
                            recommendations.append(
                                f"Consider alternatives for {parent} to avoid its incompatible dependency {package_info}"
                            )

                    reasoning.append(reason)

                elif package.get("compatible") == "partial":
                    package_info = f"{package['name']}{package.get('version_spec', '')}"
                    if package.get("direct", True):
                        reason = f"Python package {package_info} may have ARM64 compatibility issues: {package.get('reason')}"
                        recommendations.append(
                            f"Test {package_info} on ARM64 and check for compatibility issues in {file_path}"
                        )
                    else:
                        parent = package.get("parent", "unknown parent")
                        reason = f"Transitive dependency {package_info} (required by {parent}) may have ARM64 compatibility issues: {package.get('reason')}"
                        recommendations.append(
                            f"Test {parent} with its dependency {package_info} on ARM64 for compatibility"
                        )

                    reasoning.append(reason)

        elif file_name == "package.json":
            # Analyze JavaScript dependencies from package.json
            content = dep_analysis.get("content", "")
            if not content:
                continue

            # Analyze the package.json content
            js_packages = analyze_package_json(content)

            for package in js_packages:
                package["file"] = file_path
                dependency_results.append(package)

                # Generate recommendations for JS packages
                if package.get("compatible") is False:
                    package_info = f"{package['name']}@{package.get('version', '')}"
                    reason = f"JavaScript package {package_info} is not compatible with ARM64: {package.get('reason')}"
                    recommendations.append(
                        f"Replace {package_info} with an ARM64 compatible alternative in {file_path}"
                    )
                    reasoning.append(reason)

                elif package.get("compatible") == "partial":
                    package_info = f"{package['name']}@{package.get('version', '')}"
                    reason = f"JavaScript package {package_info} may have ARM64 compatibility issues: {package.get('reason')}"

                    if package.get("dev_dependency", False):
                        recommendations.append(
                            f"Test dev dependency {package_info} on ARM64 (may only affect build environment)"
                        )
                    else:
                        recommendations.append(
                            f"Test {package_info} on ARM64 and check for native code compatibility issues"
                        )

                    reasoning.append(reason)

    # De-duplicate recommendations
    unique_recommendations = list(dict.fromkeys(recommendations))

    return {
        "dependencies": dependency_results,
        "recommendations": unique_recommendations,
        "reasoning": reasoning,
    }


if __name__ == "__main__":

    content = """
    thrift
    tensorflow-data-validation
    """

    # 의존성 분석 실행
    dependency_analysis = analyze_requirements_with_pipgrip(content)

    # 결과 출력
    print(dependency_analysis)

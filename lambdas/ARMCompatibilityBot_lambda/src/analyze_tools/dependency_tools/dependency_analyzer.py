import re
import subprocess
import tempfile
import logging
from typing import Dict, List, Any
import os
import sys

sys.path.append(os.path.dirname("/Users/woohyeok/development/2025/alpha/"))

# Import the package compatibility checker
from analyze_tools.dependency_tools.python.python_package_compatibility import (
    check_python_package_compatibility,
)

# Import the JavaScript compatibility checker
from analyze_tools.dependency_tools.js_compatibility import analyze_package_json

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_dependency_compatibility(dependency_analysis):
    """
    Analyze dependencies for ARM compatibility.
    """
    dependency_results = []
    recommendations = []
    reasoning = []

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

            # Use enhanced analysis
            packages = _analyze_requirements(content)

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

    # Remove duplicate dependencies
    unique_keys = set()
    deduplicated_results = []
    for package in dependency_results:
        key = (package.get("name"), package.get("version_spec", package.get("version")))
        if key not in unique_keys:
            unique_keys.add(key)
            deduplicated_results.append(package)

    # De-duplicate recommendations
    unique_recommendations = list(dict.fromkeys(recommendations))

    return {
        "dependencies": deduplicated_results,  # Use deduplicated list
        "recommendations": unique_recommendations,
        "reasoning": reasoning,
    }


def _analyze_requirements(content: str) -> List[Dict[str, Any]]:
    """
    Analyze a requirements.txt file
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

    try:
        # Process direct dependencies first
        for package_name, version_spec, original_line in direct_dependencies:
            clean_name = _clean_package_name(package_name)

            # Check compatibility
            compatibility_result = check_python_package_compatibility(
                package_name, version_spec, original_line, direct=True
            )
            results.append(compatibility_result)

    except Exception as e:
        logger.error(f"Error in dependency resolution: {str(e)}")

    return results


def _clean_package_name(name: str) -> str:
    """Clean package name by removing version specifiers."""
    return re.sub(r"[=<>!~].*$", "", name.strip().lower())


if __name__ == "__main__":

    content = """
    thrift
    tensorflow-data-validation
    """

    # 의존성 분석 실행
    dependency_analysis = _analyze_requirements(content)

    # 결과 출력
    print(dependency_analysis)

"""
Dependency analysis tools for ARM64 compatibility checking
"""

from analyze_tools.dependency_tools.dependency_analyzer import (
    analyze_dependency_compatibility,
    analyze_requirements_with_pipgrip,
)

from analyze_tools.dependency_tools.package_compatibility import (
    check_pypi_package_arm_compatibility,
)

from analyze_tools.dependency_tools.js_compatibility import (
    check_npm_package_arm_compatibility,
    analyze_package_json,
)

__all__ = [
    "analyze_dependency_compatibility",
    "analyze_requirements_with_pipgrip",
    "check_pypi_package_arm_compatibility",
    "check_npm_package_arm_compatibility",
    "analyze_package_json",
]

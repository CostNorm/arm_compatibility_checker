"""
ARM64 Compatibility Analysis Tools

This package provides tools to analyze various aspects of code repositories
for ARM64 compatibility, including Terraform resources, Docker images,
and Python dependencies.
"""

# Import main functions to expose at package level
from analyze_tools.compatibility_checker import check_arm_compatibility
from analyze_tools.terraform_tools.terraform_analyzer import (
    analyze_terraform_compatibility,
)
from analyze_tools.docker_tools.docker_analyzer import analyze_docker_compatibility
from analyze_tools.dependency_tools.dependency_analyzer import (
    analyze_dependency_compatibility,
)

__all__ = [
    "check_arm_compatibility",
    "analyze_terraform_compatibility",
    "analyze_docker_compatibility",
    "analyze_dependency_compatibility",
]

"""
Terraform analysis tools for ARM64 compatibility checking
"""

from analyze_tools.terraform_tools.terraform_analyzer import (
    analyze_terraform_compatibility,
    is_instance_type_arm_compatible,
)

__all__ = ["analyze_terraform_compatibility", "is_instance_type_arm_compatible"]

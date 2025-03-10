def is_instance_type_arm_compatible(instance_type):
    """Check if an AWS instance type is ARM compatible or can be migrated to ARM."""

    # ARM-based instance families
    arm_families = [
        "a1",
        "t4g",
        "m6g",
        "m7g",
        "c6g",
        "c7g",
        "r6g",
        "r7g",
        "x2gd",
        "im4gn",
    ]

    # X86-only instance families
    x86_only_families = ["mac", "f1", "p2", "p3", "g3", "g4", "inf"]

    # Check if it's already an ARM instance
    if any(instance_type.startswith(family) for family in arm_families):
        return {"compatible": True, "already_arm": True}

    # Check if it's in a family that has no ARM equivalent
    if any(instance_type.startswith(family) for family in x86_only_families):
        return {"compatible": False, "reason": "No ARM equivalent available"}

    # For standard instance types, suggest ARM equivalents
    instance_mapping = {
        "t3": "t4g",
        "t2": "t4g",
        "m5": "m6g",
        "m4": "m6g",
        "c5": "c6g",
        "c4": "c6g",
        "r5": "r6g",
        "r4": "r6g",
    }

    for x86_family, arm_family in instance_mapping.items():
        if instance_type.startswith(x86_family):
            # Get the size part of the instance type (e.g., "large" from "t3.large")
            size = instance_type[len(x86_family) :]
            if size.startswith("."):
                size = size[1:]  # Remove the leading dot

            return {
                "compatible": True,
                "already_arm": False,
                "suggestion": f"{arm_family}.{size}",
                "current": instance_type,
            }

    # Default to potentially compatible but requiring further analysis
    return {
        "compatible": "unknown",
        "current": instance_type,
        "reason": "Requires manual verification",
    }


def analyze_terraform_compatibility(terraform_analysis):
    """
    Analyze Terraform files for ARM compatibility
    """
    terraform_results = []
    recommendations = []
    reasoning = []

    for tf_analysis in terraform_analysis:
        file_path = tf_analysis.get("file", "unknown")
        for instance_type in tf_analysis.get("analysis", {}).get("instance_types", []):
            compatibility = is_instance_type_arm_compatible(instance_type)
            compatibility["file"] = file_path
            terraform_results.append(compatibility)

            # Add reasoning for this instance type
            reason = ""
            if compatibility.get("already_arm", False):
                reason = f"Instance type {instance_type} is already ARM-based and fully compatible."
            elif compatibility.get("compatible") is True and compatibility.get(
                "suggestion"
            ):
                reason = f"Instance type {instance_type} can be replaced with ARM equivalent {compatibility['suggestion']}."
            elif compatibility.get("compatible") is False:
                reason = f"Instance type {instance_type} has no ARM equivalent: {compatibility.get('reason', 'Unknown reason')}."
            else:
                reason = f"Instance type {instance_type} requires manual verification for ARM compatibility."

            reasoning.append(reason)

            if compatibility.get("suggestion"):
                recommendations.append(
                    f"Replace {instance_type} with {compatibility['suggestion']} in {file_path}"
                )

    return {
        "instance_types": terraform_results,
        "recommendations": recommendations,
        "reasoning": reasoning,
    }

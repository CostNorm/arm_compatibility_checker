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


def check_arm_compatibility(analysis_results):
    """
    Check ARM64 compatibility based on the analysis results from terraform files,
    dockerfiles, and dependency files.
    """
    compatibility_result = {
        "overall_compatibility": None,
        "instance_types": [],
        "docker_images": [],
        "dependencies": [],
        "recommendations": [],
    }

    # Check instance types from Terraform
    for tf_analysis in analysis_results.get("terraform_analysis", []):
        file_path = tf_analysis.get("file", "unknown")
        for instance_type in tf_analysis.get("analysis", {}).get("instance_types", []):
            compatibility = is_instance_type_arm_compatible(instance_type)
            compatibility["file"] = file_path
            compatibility_result["instance_types"].append(compatibility)

            if compatibility.get("suggestion"):
                compatibility_result["recommendations"].append(
                    f"Replace {instance_type} with {compatibility['suggestion']} in {file_path}"
                )

    # Check Docker images
    for docker_analysis in analysis_results.get("dockerfile_analysis", []):
        file_path = docker_analysis.get("file", "unknown")
        for base_image in docker_analysis.get("analysis", {}).get("base_images", []):
            image_compatibility = {"image": base_image, "file": file_path}

            # Check if image explicitly specifies architecture
            if "arm64" in base_image or "arm/v" in base_image:
                image_compatibility["compatible"] = True
                image_compatibility["already_arm"] = True
            elif "amd64" in base_image or "x86_64" in base_image:
                image_compatibility["compatible"] = False
                image_compatibility["reason"] = "Explicitly uses x86 architecture"
                compatibility_result["recommendations"].append(
                    f"Change base image {base_image} to an ARM64 compatible version in {file_path}"
                )
            else:
                # Common images that offer ARM support
                common_arm_images = [
                    "alpine",
                    "ubuntu",
                    "python",
                    "node",
                    "golang",
                    "amazon/aws-cli",
                ]
                if any(img in base_image.lower() for img in common_arm_images):
                    image_compatibility["compatible"] = True
                    image_compatibility["suggestion"] = (
                        f"Add platform specification: --platform=linux/arm64 for {base_image}"
                    )
                    compatibility_result["recommendations"].append(
                        image_compatibility["suggestion"]
                    )
                else:
                    image_compatibility["compatible"] = "unknown"
                    image_compatibility["reason"] = "Manual verification needed"
                    compatibility_result["recommendations"].append(
                        f"Verify if {base_image} has ARM64 support in {file_path}"
                    )

            compatibility_result["docker_images"].append(image_compatibility)

    # Check dependencies
    for dep_analysis in analysis_results.get("dependency_analysis", []):
        file_path = dep_analysis.get("file", "unknown")
        for arch_dep in dep_analysis.get("analysis", {}).get("arch_specific", []):
            dependency = {
                "dependency": arch_dep,
                "file": file_path,
                "compatible": False,
            }
            compatibility_result["dependencies"].append(dependency)
            compatibility_result["recommendations"].append(
                f"Check compatibility of dependency {arch_dep} in {file_path}"
            )

    # Determine overall compatibility
    if (
        not compatibility_result["instance_types"]
        and not compatibility_result["docker_images"]
        and not compatibility_result["dependencies"]
    ):
        compatibility_result["overall_compatibility"] = "unknown"
        compatibility_result["recommendations"].append(
            "No clear architecture-specific elements found. Manual verification recommended."
        )
    else:
        # Check if there are any incompatible elements
        has_incompatible = any(
            item.get("compatible") is False
            for category in ["instance_types", "docker_images", "dependencies"]
            for item in compatibility_result[category]
        )

        if has_incompatible:
            compatibility_result["overall_compatibility"] = "incompatible"
        else:
            compatibility_result["overall_compatibility"] = "compatible"

    return compatibility_result

def is_docker_image_arm_compatible(base_image):
    """Check if a Docker image is ARM compatible."""

    # Check if image explicitly specifies architecture
    if "arm64" in base_image or "arm/v" in base_image:
        return {"image": base_image, "compatible": True, "already_arm": True}
    elif "amd64" in base_image or "x86_64" in base_image:
        return {
            "image": base_image,
            "compatible": False,
            "reason": "Explicitly uses x86 architecture",
        }
    else:
        # Common images that offer ARM support
        common_arm_images = [
            "alpine",
            "ubuntu",
            "python",
            "node",
            "golang",
            "amazon/aws-cli",
            "debian",
            "centos",
            "fedora",
            "amazonlinux",
            "nginx",
            "redis",
            "postgres",
            "mysql",
            "mongo",
        ]
        if any(img in base_image.lower() for img in common_arm_images):
            return {
                "image": base_image,
                "compatible": True,
                "suggestion": f"Add platform specification: --platform=linux/arm64 for {base_image}",
            }
        else:
            return {
                "image": base_image,
                "compatible": "unknown",
                "reason": "Manual verification needed",
            }


def analyze_docker_compatibility(dockerfile_analysis):
    """
    Analyze Dockerfiles for ARM compatibility
    """
    docker_results = []
    recommendations = []
    reasoning = []

    for docker_analysis in dockerfile_analysis:
        file_path = docker_analysis.get("file", "unknown")
        for base_image in docker_analysis.get("analysis", {}).get("base_images", []):
            compatibility = is_docker_image_arm_compatible(base_image)
            compatibility["file"] = file_path
            docker_results.append(compatibility)

            # Add reasoning for this docker image
            if compatibility.get("already_arm", False):
                reason = f"Docker image {base_image} explicitly uses ARM64 architecture and is fully compatible."
                reasoning.append(reason)
            elif compatibility.get("compatible") is False:
                reason = f"Docker image {base_image} explicitly uses x86 architecture and is incompatible with ARM64."
                recommendations.append(
                    f"Change base image {base_image} to an ARM64 compatible version in {file_path}"
                )
                reasoning.append(reason)
            elif compatibility.get("compatible") is True:
                reason = f"Docker image {base_image} is from a common repository that supports ARM64, but platform specification is recommended."
                recommendations.append(compatibility["suggestion"])
                reasoning.append(reason)
            else:
                reason = f"Docker image {base_image} has unknown ARM64 compatibility status and requires manual verification."
                recommendations.append(
                    f"Verify if {base_image} has ARM64 support in {file_path}"
                )
                reasoning.append(reason)

    return {
        "docker_images": docker_results,
        "recommendations": recommendations,
        "reasoning": reasoning,
    }

import re
import json


def extract_instance_types_from_terraform_file(content):
    """
    Analyze Terraform file content for instance types and other ARM64
    compatibility indicators.
    """
    results = {"instance_types": [], "other_indicators": []}

    # Look for AWS instance types in instance_type assignments
    instance_type_pattern = r'instance_type\s*=\s*"([^"]+)"'
    matches = re.findall(instance_type_pattern, content)

    if matches:
        results["instance_types"] = matches

    # Look for architecture-specific resources or configurations
    arch_indicators = ["architecture", "amd64", "x86_64", "arm64", "graviton"]

    for indicator in arch_indicators:
        if indicator in content.lower():
            results["other_indicators"].append(indicator)

    return results


def parse_dockerfile_content(content):
    """
    Analyze Dockerfile content for base image architecture and other
    ARM64 compatibility indicators.
    """
    results = {"base_images": [], "arch_commands": []}

    # Extract FROM commands for base images
    from_pattern = r"FROM\s+([^\s]+)"
    base_images = re.findall(from_pattern, content)
    results["base_images"] = base_images

    # Look for architecture-specific commands
    arch_keywords = ["amd64", "x86_64", "arm64", "arm/v", "graviton", "--platform"]

    for line in content.splitlines():
        for keyword in arch_keywords:
            if keyword.lower() in line.lower():
                results["arch_commands"].append(line.strip())
                break

    return results


def extract_dependencies(content, file_type):
    """
    Extract dependencies from requirements.txt and package.json files
    """
    results = {"dependencies": [], "content": content}

    if file_type == "txt":  # requirements.txt
        # Extract package names and versions
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                results["dependencies"].append(line)
    elif file_type == "json":  # package.json
        # For package.json, we'll just store the content and let the analyzer handle it
        try:
            # Basic validation of JSON
            package_data = json.loads(content)
            # Extract dependency names for initial analysis
            deps = package_data.get("dependencies", {})
            dev_deps = package_data.get("devDependencies", {})

            # Add all dependencies to the results
            for name, version in deps.items():
                results["dependencies"].append(f"{name}@{version}")

            for name, version in dev_deps.items():
                results["dependencies"].append(f"{name}@{version} (dev)")

        except json.JSONDecodeError:
            results["dependencies"].append("Invalid JSON format")

    return results

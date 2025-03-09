import re
import json


def analyze_terraform_file(content):
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


def analyze_dockerfile(content):
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


def analyze_dependencies(content, file_type):
    """
    Analyze dependency files (requirements.txt, package.json, etc.)
    for architecture-specific dependencies.
    """
    results = {"dependencies": [], "arch_specific": []}

    if file_type == "txt":  # requirements.txt
        # Extract package names and versions
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                results["dependencies"].append(line)
                # Check for known problematic packages for ARM64
                if any(
                    pkg in line.lower()
                    for pkg in ["tensorflow<2", "torch<1.9", "nvidia-", "cuda"]
                ):
                    results["arch_specific"].append(line)

    elif file_type == "json":  # package.json
        try:
            package_data = json.loads(content)
            dependencies = package_data.get("dependencies", {})
            dev_dependencies = package_data.get("devDependencies", {})

            # Combine all dependencies
            all_deps = {}
            all_deps.update(dependencies)
            all_deps.update(dev_dependencies)

            for pkg, version in all_deps.items():
                dep_entry = f"{pkg}@{version}"
                results["dependencies"].append(dep_entry)

                # Check for packages with native bindings that might have ARM issues
                if any(
                    p in pkg.lower() for p in ["node-sass", "sharp", "canvas", "grpc"]
                ):
                    results["arch_specific"].append(dep_entry)
        except json.JSONDecodeError:
            results["error"] = "Invalid JSON format"

    elif file_type in ["xml", "gradle"]:
        # For Maven pom.xml or build.gradle files, just do basic text analysis
        for line in content.splitlines():
            line = line.strip()
            if any(
                lib in line.lower()
                for lib in ["native", "jni", "x86", "amd64", "intel", "arm", "graviton"]
            ):
                results["arch_specific"].append(line)

    return results

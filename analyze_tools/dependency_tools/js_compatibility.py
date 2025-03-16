import json
import logging
import requests
from typing import Dict, List, Any, Union

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for NPM package information to avoid repeated API calls
NPM_CACHE = {}


def check_npm_package_arm_compatibility(
    package_name: str, package_version: str = None
) -> Dict[str, Any]:
    """
    Check if an NPM package is compatible with ARM64 architecture.

    Args:
        package_name (str): Name of the npm package
        package_version (str, optional): Specific version to check

    Returns:
        dict: Compatibility information
    """
    cache_key = f"{package_name}@{package_version}" if package_version else package_name
    if cache_key in NPM_CACHE:
        return NPM_CACHE[cache_key]

    # Known problematic packages for ARM64
    problematic_packages = [
        "node-sass",
        "sharp",
        "canvas",
        "grpc",
        "electron",
        "node-gyp",
        "robotjs",
        "sqlite3",
        "bcrypt",
        "cpu-features",
        "node-expat",
        "dtrace-provider",
        "epoll",
        "fsevents",
        "libxmljs",
        "leveldown",
    ]

    # Packages that are usually just JavaScript and compatible
    known_compatible = [
        "react",
        "react-dom",
        "lodash",
        "axios",
        "express",
        "moment",
        "chalk",
        "commander",
        "dotenv",
        "uuid",
        "cors",
        "typescript",
        "jest",
        "mocha",
        "eslint",
        "prettier",
        "babel",
        "webpack",
        "rollup",
        "vite",
    ]

    try:
        # Check if it's in our known lists
        if any(package_name.lower() == p.lower() for p in problematic_packages):
            result = {
                "compatible": "partial",
                "reason": "Package likely contains native code that needs to be compiled for ARM64",
            }
        elif any(package_name.lower() == p.lower() for p in known_compatible):
            result = {
                "compatible": True,
                "reason": "Package is pure JavaScript and should work on any architecture",
            }
        else:
            # Check with npm registry
            url = f"https://registry.npmjs.org/{package_name}"
            if package_version:
                url = f"{url}/{package_version}"

            response = requests.get(url, timeout=5)

            if response.status_code != 200:
                return {
                    "compatible": "unknown",
                    "reason": f"Package not found or npm registry error: {response.status_code}",
                }

            data = response.json()

            # Look for native dependencies in package.json
            has_native_deps = False
            has_binary_field = False

            if "dependencies" in data:
                for dep in data["dependencies"]:
                    if any(p in dep.lower() for p in problematic_packages):
                        has_native_deps = True
                        break

            if "binary" in data or "gypfile" in data:
                has_binary_field = True

            if has_binary_field:
                result = {
                    "compatible": "partial",
                    "reason": "Package has binary/gyp fields indicating native code",
                }
            elif has_native_deps:
                result = {
                    "compatible": "partial",
                    "reason": "Package depends on modules with native code",
                }
            else:
                result = {
                    "compatible": True,
                    "reason": "Package appears to be pure JavaScript with no native dependencies",
                }

        # Cache the result
        NPM_CACHE[cache_key] = result
        return result

    except Exception as e:
        logger.error(f"Error checking {package_name}: {str(e)}")
        return {
            "compatible": "unknown",
            "reason": f"Error checking compatibility: {str(e)}",
        }


def analyze_package_json(content: str) -> List[Dict[str, Any]]:
    """
    Analyze a package.json file for ARM64 compatibility issues.

    Args:
        content (str): Content of package.json file

    Returns:
        List[Dict[str, Any]]: List of dependency compatibility information
    """
    results = []

    try:
        package_data = json.loads(content)
        dependencies = package_data.get("dependencies", {})
        dev_dependencies = package_data.get("devDependencies", {})

        # Process all dependencies
        all_deps = {}
        all_deps.update(dependencies)
        all_deps.update(dev_dependencies)

        for pkg, ver in all_deps.items():
            # Clean version string
            version = ver.lstrip("^~=v")

            # Check compatibility
            compatibility = check_npm_package_arm_compatibility(pkg, version)

            # Add to results
            results.append(
                {
                    "dependency": f"{pkg}@{ver}",
                    "name": pkg,
                    "version": version,
                    "compatible": compatibility.get("compatible", "unknown"),
                    "reason": compatibility.get("reason", "Unknown"),
                    "direct": True,  # All packages in package.json are direct dependencies
                    "dev_dependency": pkg in dev_dependencies,
                }
            )

    except json.JSONDecodeError:
        results.append(
            {
                "dependency": "Invalid JSON",
                "compatible": "unknown",
                "reason": "Invalid JSON format in package.json",
            }
        )
    except Exception as e:
        logger.error(f"Error analyzing package.json: {str(e)}")
        results.append(
            {
                "dependency": "Error",
                "compatible": "unknown",
                "reason": f"Error analyzing package.json: {str(e)}",
            }
        )

    return results

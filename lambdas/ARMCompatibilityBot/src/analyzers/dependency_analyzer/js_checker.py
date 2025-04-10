import json
import logging
import requests
from typing import Dict, List, Any, Optional

from .base_checker import BaseDependencyChecker

logger = logging.getLogger(__name__)

# --- Module-level Cache ---
# Cache for NPM package information {cache_key: result}
_NPM_CACHE: Dict[str, Dict[str, Any]] = {}

# --- Known Package Lists (Module Level) ---
# Known problematic packages for ARM64 (often contain native code)
_PROBLEMATIC_PACKAGES = [
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
    # Add others as identified
]

# Packages generally known to be pure JavaScript and compatible
_KNOWN_COMPATIBLE_JS = [
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
    "next",
    "vue",
    "angular",
    "jquery",
    "redux",
    "react-router-dom",
    "classnames",
    # Add others as needed
]


class JSDependencyChecker(BaseDependencyChecker):
    """Checks JavaScript dependencies (from package.json) for ARM64 compatibility."""

    def parse_dependencies(
        self, file_content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Parses dependencies from package.json content.

        Args:
            file_content: Content of the package.json file.
            file_path: Path to the package.json file.

        Returns:
            List of dictionaries, each representing a dependency.
            Example: [{'name': 'react', 'version_spec': '^18.0.0', 'dev_dependency': False, 'file': 'package.json'}]
        """
        parsed_deps = []
        logger.debug(f"Parsing dependencies from: {file_path}")
        try:
            package_data = json.loads(file_content)
            dependencies = package_data.get("dependencies", {})
            dev_dependencies = package_data.get("devDependencies", {})

            for name, version_spec in dependencies.items():
                parsed_deps.append(
                    {
                        "name": name,
                        "version_spec": version_spec,  # Keep original specifier
                        "dev_dependency": False,
                        "file": file_path,
                    }
                )

            for name, version_spec in dev_dependencies.items():
                parsed_deps.append(
                    {
                        "name": name,
                        "version_spec": version_spec,
                        "dev_dependency": True,
                        "file": file_path,
                    }
                )

            logger.info(f"Parsed {len(parsed_deps)} dependencies from {file_path}.")

        except json.JSONDecodeError:
            logger.error(
                f"Invalid JSON format in {file_path}. Cannot parse dependencies."
            )
            # Return an empty list or a special marker? Empty list is safer.
            return []
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}", exc_info=True)
            return []

        return parsed_deps

    def check_compatibility(self, dependency_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Checks the ARM compatibility of a single JS dependency using heuristics and NPM registry info.

        Args:
            dependency_info: Dictionary containing 'name', 'version_spec', 'dev_dependency', 'file'.

        Returns:
            Dictionary with compatibility status ('compatible', 'reason', etc.).
        """
        package_name = dependency_info.get("name")
        version_spec = dependency_info.get(
            "version_spec", ""
        )  # Original specifier like ^1.0.0
        # Attempt to clean version spec for API lookup (best effort)
        # Removes common prefixes, but might not handle complex ranges perfectly for API calls
        version_lookup = version_spec.lstrip("^~=v ") if version_spec else None

        logger.debug(
            f"Checking compatibility for JS package: {package_name} {version_spec or ''}"
        )

        # Call the internal check function
        compatibility_result = self._check_npm_package_compatibility(
            package_name, version_lookup
        )

        # Combine results
        return {
            **dependency_info,  # Include name, version_spec, file, dev_dependency
            "compatible": compatibility_result.get("compatible", "unknown"),
            "reason": compatibility_result.get("reason", "Unknown"),
            # Add 'dependency' field for consistency with Python output if needed by aggregator
            "dependency": f"{package_name}@{version_spec}",
            "debug_info": compatibility_result.get(
                "debug_info"
            ),  # Pass along any debug info
        }

    def _check_npm_package_compatibility(
        self, package_name: str, package_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Internal helper to check if an NPM package is compatible with ARM64.
        Uses heuristics and fetches data from NPM registry. Caches results.

        Args:
            package_name: Name of the npm package.
            package_version: Specific version string (cleaned, optional) for API lookup.

        Returns:
            dict: Compatibility information ('compatible', 'reason').
        """
        global _NPM_CACHE
        # Use original name + specific version (if provided) for cache key
        cache_key = (
            f"{package_name}@{package_version}" if package_version else package_name
        )
        if cache_key in _NPM_CACHE:
            logger.debug(f"Using cached NPM result for {cache_key}")
            return _NPM_CACHE[cache_key]

        logger.debug(
            f"Checking NPM compatibility for {package_name} (Version hint: {package_version or 'latest'})"
        )
        result: Dict[str, Any] = {"compatible": "unknown", "reason": "Initial state"}
        debug_info = {"source": "unknown", "details": None}

        package_name_lower = package_name.lower()

        try:
            # 1. Check known lists (Heuristics)
            if any(package_name_lower == p for p in _PROBLEMATIC_PACKAGES):
                result = {
                    "compatible": "partial",
                    "reason": "Package is known to often contain native code requiring ARM64 compilation/binaries.",
                }
                debug_info["source"] = "heuristic_problematic"
            elif any(package_name_lower == p for p in _KNOWN_COMPATIBLE_JS):
                result = {
                    "compatible": True,
                    "reason": "Package is generally pure JavaScript and architecture-independent.",
                }
                debug_info["source"] = "heuristic_compatible"
            else:
                # 2. Check NPM Registry (if not found in heuristics)
                debug_info["source"] = "npm_registry"
                # Use registry URL format (package name might need encoding for scoped packages, but requests usually handles it)
                url_pkg_name = package_name.replace(
                    "/", "%2F"
                )  # Basic encoding for scoped packages
                url = f"https://registry.npmjs.org/{url_pkg_name}"
                # Fetching specific version info can be complex due to version ranges.
                # Fetching the general package info is usually sufficient to check for native indicators.
                # If a specific version was provided, we could try fetching that endpoint, but it might 404 often.
                # url = f"{url}/{package_version}" if package_version else url # Option to check specific version

                try:
                    response = requests.get(url, timeout=10)
                    debug_info["details"] = {
                        "url": url,
                        "status_code": response.status_code,
                    }

                    if response.status_code == 200:
                        data = response.json()
                        latest_version_info = (
                            data.get("versions", {}).get(
                                data.get("dist-tags", {}).get("latest")
                            )
                            if data.get("versions")
                            else data
                        )  # Get latest info

                        if latest_version_info:
                            # Look for indicators of native code in the latest version's data
                            has_gypfile = latest_version_info.get("gypfile", False)
                            scripts = latest_version_info.get("scripts", {})
                            has_install_script = (
                                "install" in scripts
                                or "preinstall" in scripts
                                or "postinstall" in scripts
                            )
                            # Check cpu/os fields (less common but indicative)
                            cpu_field = latest_version_info.get("cpu")
                            os_field = latest_version_info.get("os")
                            # Check dependencies for known problematic ones
                            dependencies = latest_version_info.get("dependencies", {})
                            has_problematic_dep = any(
                                p in dependencies for p in _PROBLEMATIC_PACKAGES
                            )

                            if has_gypfile or (
                                has_install_script and "node-gyp" in json.dumps(scripts)
                            ):
                                result = {
                                    "compatible": "partial",
                                    "reason": "Package likely uses node-gyp for native compilation.",
                                }
                                debug_info["details"][
                                    "indicator"
                                ] = "gypfile or install script"
                            elif cpu_field and not any(
                                arch in cpu_field for arch in ["arm", "arm64", "!x64"]
                            ):  # Checks if CPU field exists and doesn't explicitly allow ARM
                                result = {
                                    "compatible": "partial",
                                    "reason": f"Package specifies CPU compatibility ({cpu_field}) that may exclude ARM64.",
                                }
                                debug_info["details"]["indicator"] = "cpu field"
                            elif os_field and not any(
                                op_sys in os_field
                                for op_sys in ["!win32", "!darwin", "linux"]
                            ):  # Checks if OS field exists and doesn't explicitly allow linux/others
                                result = {
                                    "compatible": "partial",
                                    "reason": f"Package specifies OS compatibility ({os_field}) that may indicate issues.",
                                }
                                debug_info["details"]["indicator"] = "os field"
                            elif has_problematic_dep:
                                result = {
                                    "compatible": "partial",
                                    "reason": "Package depends on other modules known to have native code issues.",
                                }
                                debug_info["details"][
                                    "indicator"
                                ] = "problematic dependency"
                            else:
                                result = {
                                    "compatible": True,
                                    "reason": "Package appears to be pure JavaScript based on registry data.",
                                }
                                debug_info["details"][
                                    "indicator"
                                ] = "no native indicators found"
                        else:
                            result = {
                                "compatible": "unknown",
                                "reason": "Could not retrieve detailed version info from NPM registry.",
                            }

                    elif response.status_code == 404:
                        result = {
                            "compatible": "unknown",
                            "reason": f"Package '{package_name}' not found on NPM registry.",
                        }
                    else:
                        result = {
                            "compatible": "unknown",
                            "reason": f"NPM registry error: HTTP {response.status_code}",
                        }

                except requests.exceptions.RequestException as req_err:
                    logger.warning(
                        f"Network error checking NPM for {package_name}: {req_err}"
                    )
                    result = {
                        "compatible": "unknown",
                        "reason": f"Network error checking NPM: {req_err}",
                    }
                    debug_info["details"] = {"error": str(req_err)}
                except json.JSONDecodeError as json_err:
                    logger.warning(
                        f"Failed to parse NPM registry response for {package_name}: {json_err}"
                    )
                    result = {
                        "compatible": "unknown",
                        "reason": "Failed to parse NPM registry response.",
                    }
                    debug_info["details"] = {"error": str(json_err)}

            # Add debug info to the final result
            result["debug_info"] = debug_info
            # Cache the result
            _NPM_CACHE[cache_key] = result
            logger.debug(f"NPM check result for {cache_key}: {result}")
            return result

        except Exception as e:
            logger.error(
                f"Unexpected error checking JS compatibility for {package_name}: {e}",
                exc_info=True,
            )
            result = {
                "compatible": "unknown",
                "reason": f"Unexpected error during JS compatibility check: {e}",
            }
            result["debug_info"] = {"source": "error", "details": {"error": str(e)}}
            # Cache the error result? Maybe not, allow retry later.
            # _NPM_CACHE[cache_key] = result
            return result

import json
import logging
import requests
from typing import Optional, Dict, Any, List

# Correct import for recent packaging versions
from packaging.utils import canonicalize_name
from packaging.version import parse as parse_version, InvalidVersion
from packaging.specifiers import SpecifierSet, InvalidSpecifier

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for PyPI package information to avoid repeated API calls
PYPI_CACHE = {}


def check_pypi_package_arm_compatibility(
    package_name: str, package_version_specifier: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check if a PyPI package, potentially with a version specifier, is compatible
    with ARM64 architecture. Uses PyPI API and the packaging library.

    Args:
        package_name (str): Name of the package (e.g., "tensorflow_datasets").
        package_version_specifier (str, optional): Version constraint
            (e.g., "==1.2.3", ">=1.20", "<=2.0,>1.0"). Defaults to None (latest).

    Returns:
        dict: {"compatible": bool or "partial" or "unknown", "reason": str,
               "checked_version": str or None}
    """
    try:
        # 1. Canonicalize package name (e.g., tensorflow_datasets -> tensorflow-datasets)
        # Use canonicalize_name instead of normalize_name
        normalized_name = canonicalize_name(package_name)
    except Exception as e:  # Catch potential errors in canonicalization itself
        logger.error(f"Error canonicalizing package name '{package_name}': {e}")
        return {
            "compatible": "unknown",
            "reason": f"Invalid package name format: {package_name}",
            "checked_version": None,
        }

    # 2. Create cache key using canonicalized name and specifier
    cache_key = (
        f"{normalized_name}@{package_version_specifier}"
        if package_version_specifier
        else normalized_name
    )
    if cache_key in PYPI_CACHE:
        logger.debug(f"Using cached result for {cache_key}")
        return PYPI_CACHE[cache_key]

    logger.info(
        f"Checking PyPI compatibility for: {normalized_name}"
        f"{'@' + package_version_specifier if package_version_specifier else ' (latest)'}"
    )

    try:
        # 3. Fetch package data from PyPI JSON API (always fetch base URL for all versions)
        url = f"https://pypi.org/pypi/{normalized_name}/json"
        response = requests.get(url, timeout=10)  # Increased timeout slightly

        if response.status_code == 404:
            logger.warning(f"Package {normalized_name} not found on PyPI.")
            # Cache the "not found" result to avoid repeated checks
            result_not_found = {
                "compatible": "unknown",
                "reason": f"Package '{normalized_name}' not found on PyPI.",
                "checked_version": None,
            }
            PYPI_CACHE[cache_key] = result_not_found
            return result_not_found
        elif response.status_code != 200:
            logger.error(
                f"Failed to fetch package info for {normalized_name}: HTTP {response.status_code}"
            )
            # Don't cache transient API errors as aggressively? Or cache with short TTL?
            # For now, return without caching.
            return {
                "compatible": "unknown",
                "reason": f"PyPI API error for '{normalized_name}': HTTP {response.status_code}",
                "checked_version": None,
            }

        data = response.json()
        available_versions_str = list(data.get("releases", {}).keys())

        # 4. Determine the target version to check
        target_version_str: Optional[str] = None
        specifier_set: Optional[SpecifierSet] = None

        if package_version_specifier:
            try:
                # Allow comma-separated specifiers like "<=2.0,>1.0"
                specifier_set = SpecifierSet(package_version_specifier)
            except InvalidSpecifier:
                logger.error(
                    f"Invalid version specifier '{package_version_specifier}' for {normalized_name}"
                )
                result_invalid_spec = {
                    "compatible": "unknown",
                    "reason": f"Invalid version specifier: '{package_version_specifier}'",
                    "checked_version": None,
                }
                PYPI_CACHE[cache_key] = result_invalid_spec  # Cache invalid spec result
                return result_invalid_spec

            # Find the latest available version that satisfies the specifier
            latest_satisfying_version = None
            candidate_versions = []
            for v_str in available_versions_str:
                try:
                    parsed_v = parse_version(v_str)
                    # Store valid versions for filtering
                    candidate_versions.append(parsed_v)
                except InvalidVersion:
                    logger.warning(
                        f"Skipping invalid version format '{v_str}' for {normalized_name}"
                    )
                    continue  # Skip versions we can't parse

            # Filter using the specifier set. Include prereleases if the specifier allows them.
            # The `prereleases` flag in `filter` depends on whether the specifier itself includes a pre-release marker (e.g., >=1.0.0rc1)
            # We might need to explicitly allow pre-releases if the specifier doesn't contain one but we want to consider them.
            # For simplicity here, let's assume standard filtering works for most cases.
            # If you need fine-grained pre-release control, add a flag or check specifier details.
            allowed_versions = list(
                specifier_set.filter(candidate_versions, prereleases=True)
            )

            if allowed_versions:
                # Find the maximum version among the allowed ones
                target_version_str = str(max(allowed_versions))
                logger.info(
                    f"Found latest version satisfying '{package_version_specifier}': {target_version_str}"
                )
            else:
                logger.warning(
                    f"No available version of {normalized_name} satisfies specifier '{package_version_specifier}'"
                )
                available_preview = available_versions_str[
                    -5:
                ]  # Show some recent available
                result_no_satisfy = {
                    "compatible": "unknown",
                    "reason": f"No version found satisfying '{package_version_specifier}'. "
                    f"Latest available: {', '.join(available_preview)}...",
                    "checked_version": None,
                }
                PYPI_CACHE[cache_key] = (
                    result_no_satisfy  # Cache unsatisfiable spec result
                )
                return result_no_satisfy
        else:
            # No specifier provided, use the latest stable version reported by PyPI
            target_version_str = data.get("info", {}).get("version")
            if not target_version_str:
                logger.error(
                    f"Could not determine latest version for {normalized_name}"
                )
                # Don't cache if PyPI info is broken
                return {
                    "compatible": "unknown",
                    "reason": "Could not determine latest version from PyPI info.",
                    "checked_version": None,
                }
            logger.info(f"Using latest reported version: {target_version_str}")

        # 5. Analyze the release files for the target version
        if target_version_str not in data.get("releases", {}):
            logger.error(
                f"Target version {target_version_str} not found in releases dict for {normalized_name}"
            )
            # This might happen if info.version points to a pre-release not in the main list sometimes?
            # Or if specifier logic selected a version that's somehow missing.
            # Don't cache this internal inconsistency state
            return {
                "compatible": "unknown",
                "reason": f"Internal error: Target version {target_version_str} details missing.",
                "checked_version": target_version_str,
            }

        release_files = data["releases"].get(target_version_str, [])
        # Get info specific to the target version if available, otherwise use main info
        version_specific_info = (
            data.get("releases", {}).get(target_version_str, [{}])[0]
            if release_files
            else {}
        )
        info_for_version = data.get(
            "info", {}
        )  # Use main info block for classifiers etc.

        # Check if the target version itself is yanked
        yanked = version_specific_info.get("yanked", False) or any(
            f.get("yanked", False) for f in release_files
        )
        yanked_reason = version_specific_info.get("yanked_reason")
        if yanked and not yanked_reason:
            # Find the reason from the first yanked file (usually the same for all files in a yanked release)
            for f in release_files:
                if f.get("yanked", False):
                    yanked_reason = f.get("yanked_reason", "No reason provided")
                    break
        if yanked:
            logger.warning(
                f"Version {target_version_str} of {normalized_name} is yanked: {yanked_reason}"
            )

        # 6. Check for compatible wheels or source distributions
        arm_wheels = []
        universal_wheels = []
        sdist_files = []
        other_arch_wheels = []  # e.g., x86_64

        for release in release_files:
            # Skip yanked files unless we specifically want to analyze them
            if release.get("yanked", False):
                continue

            filename = release.get("filename", "")
            packagetype = release.get("packagetype", "")
            py_version_tag = release.get("python_version", "")  # e.g., 'cp39'

            if packagetype == "bdist_wheel":
                # Simple platform tag extraction (might need refinement for complex tags)
                parts = filename.rsplit("-", 3)  # try splitting by last 3 hyphens
                if len(parts) >= 3 and ".whl" in parts[-1]:
                    # platform_tag = parts[-1].split(".whl")[0]
                    # More robust: Look for known arch tags within the last part
                    wheel_tags = parts[-1].split(".whl")[
                        0
                    ]  # e.g., cp39-cp39-manylinux_2_17_aarch64.manylinux2014_aarch64
                    platform_tag_found = False

                    # Check specific ARM tags
                    if any(arm_id in wheel_tags for arm_id in ["aarch64", "arm64"]):
                        arm_wheels.append(filename)
                        platform_tag_found = True
                    # Check x86 tags
                    elif any(
                        x86_id in wheel_tags
                        for x86_id in ["win_amd64", "amd64", "x86_64", "x64"]
                    ):
                        other_arch_wheels.append(filename)
                        platform_tag_found = True
                    # Check universal tags AFTER specific ones
                    elif not platform_tag_found and any(
                        universal_id in wheel_tags
                        for universal_id in ["any", "universal2"]
                    ):
                        # Special case: universal2 on macos is good
                        if "universal2" in wheel_tags and "macosx" in wheel_tags:
                            arm_wheels.append(
                                filename
                            )  # Treat macos universal2 as ARM compatible
                        # Only count 'any' if it's not specifically for another arch (e.g. win_any - unlikely but possible)
                        elif "any" in wheel_tags and not any(
                            arch in wheel_tags for arch in ["win", "linux", "macosx"]
                        ):
                            universal_wheels.append(filename)
                        platform_tag_found = True
                    # Add more specific checks if needed (e.g., armv7l)

            elif packagetype == "sdist":
                sdist_files.append(filename)

        # 7. Determine compatibility based on findings (considering only non-yanked files)
        result = {}
        if arm_wheels:
            result = {
                "compatible": True,
                "reason": f"ARM-specific wheels found for version {target_version_str}.",
                # "details": f"Files: {', '.join(arm_wheels)}" # Optional: add detail
            }
        elif universal_wheels:
            result = {
                "compatible": True,
                "reason": f"Platform-agnostic wheels ('any') found for version {target_version_str}.",
            }
        elif sdist_files:
            # Source distribution available, check if it likely needs compilation
            classifiers = info_for_version.get("classifiers", [])
            has_c_extension = any(
                "Programming Language :: C" in c for c in classifiers
            ) or any("Programming Language :: C++" in c for c in classifiers)
            has_cython = any("Programming Language :: Cython" in c for c in classifiers)
            # Check platform markers more carefully if available
            platform_info = info_for_version.get("platform")
            is_platform_specific = (
                platform_info not in [None, "", "any"] and platform_info
            )  # Check if not None/empty/any

            if has_c_extension or has_cython or is_platform_specific:
                result = {
                    "compatible": "partial",
                    "reason": f"Source distribution found for {target_version_str}, but it may require compilation on ARM64 (contains C/C++/Cython or platform markers: '{platform_info}').",
                }
            else:
                # Pure Python sdist
                result = {
                    "compatible": True,
                    "reason": f"Likely pure Python source distribution found for {target_version_str}.",
                }
        elif other_arch_wheels:
            # Only non-ARM wheels found
            result = {
                "compatible": False,
                "reason": f"Only non-ARM wheels (e.g., x86_64) found for non-yanked files of version {target_version_str}.",
            }
        else:
            # No wheels, no sdist - potentially an issue with PyPI data or package structure, or only yanked files exist
            result = {
                "compatible": (
                    False if not yanked else "unknown"
                ),  # If yanked, status is more uncertain
                "reason": f"No non-yanked wheels or source distribution found for version {target_version_str} on PyPI.",
            }

        # Add yanked warning if applicable, even if compatibility was determined
        if yanked:
            result["warning"] = (
                f"Version {target_version_str} has been yanked: {yanked_reason}"
            )
            logger.info(
                f"Added yanked warning for {normalized_name} {target_version_str}: {result}"
            )  # Add this log

        result["checked_version"] = target_version_str

        # Cache the final result
        PYPI_CACHE[cache_key] = result
        logger.debug(
            f"Final result being returned for {cache_key}: {result}"
        )  # Add this log
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error checking {normalized_name}: {e}")
        # Don't cache network errors
        return {
            "compatible": "unknown",
            "reason": f"Network error checking PyPI: {e}",
            "checked_version": None,
        }
    except Exception as e:
        logger.exception(
            f"Unexpected error checking {normalized_name}@{package_version_specifier or 'latest'}: {e}"
        )
        # Don't cache unexpected errors
        return {
            "compatible": "unknown",
            "reason": f"Unexpected error during compatibility check: {e}",
            "checked_version": None,
        }


# --- Example Usage ---
if __name__ == "__main__":
    # Test cases
    packages_to_check = [
        ("requests", None),
        ("tensorflow_datasets", None),  # Underscore name
        ("numpy", ">=1.20,<1.22"),  # Range specifier
        ("numpy", "==1.21.0"),  # Exact version
        ("pandas", "<=1.4"),  # Upper bound
        ("cryptography", ">=35"),  # Lower bound (will likely find ARM wheels)
        ("pybloomfiltermmap3", "==0.6.0"),  # Specific old version (likely no ARM wheel)
        ("pybloom-live", None),  # Hyphen name
        ("nonexistent_package_xyz", None),  # 404 test
        ("numpy", "==99.0.0"),  # Version not satisfying
        ("oslo.utils", ">=6.0.0,<6.1.0"),  # Period in name, range
        ("elasticsearch", "==7.13.2"),  # Yanked version example
        ("protobuf", "<3.20"),  # Example with potential C++ extension sdist
    ]

    for name, spec in packages_to_check:
        print(f"\n--- Checking: {name} {spec or '(latest)'} ---")
        result = check_pypi_package_arm_compatibility(name, spec)
        print(json.dumps(result, indent=2))

    # Example of clearing cache for re-testing
    # PYPI_CACHE.clear()
    # print("\n--- Checking numpy >=1.20,<1.22 after cache clear ---")
    # result = check_pypi_package_arm_compatibility("numpy", ">=1.20,<1.22")
    # print(json.dumps(result, indent=2))

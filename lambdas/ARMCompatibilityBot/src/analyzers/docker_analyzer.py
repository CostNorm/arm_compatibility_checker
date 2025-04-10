import re
import logging
from typing import Dict, Any, List

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class DockerAnalyzer(BaseAnalyzer):
    """
    Analyzes Dockerfiles for ARM64 compatibility, focusing on base images and architecture commands.
    """

    @property
    def analysis_key(self) -> str:
        return "docker_images"

    @property
    def relevant_file_patterns(self) -> List[str]:
        # Matches 'Dockerfile', 'Dockerfile.dev', 'path/to/Dockerfile', etc. (case-insensitive)
        return [r"Dockerfile(\.\w+)?$", r".*/Dockerfile$"]

    def analyze(self, file_content: str, file_path: str) -> Dict[str, Any]:
        """
        Analyzes Dockerfile content for base images and architecture-specific commands.

        Args:
            file_content: The content of the Dockerfile.
            file_path: The path to the Dockerfile.

        Returns:
            A dictionary containing lists of found 'base_images' and 'arch_commands'.
            Example: {'base_images': ['python:3.9-slim', 'alpine:latest'], 'arch_commands': ['RUN dpkg --add-architecture arm64']}
        """
        logger.debug(f"Analyzing Dockerfile: {file_path}")
        results = {"base_images": [], "arch_commands": []}

        try:
            # Extract FROM commands for base images (case-insensitive matching for FROM)
            # Capture image name which might include registry/namespace/tag/digest
            # Example: FROM --platform=$BUILDPLATFORM python:3.9 AS builder -> python:3.9
            # Example: FROM ubuntu:22.04 -> ubuntu:22.04
            # Example: FROM public.ecr.aws/lambda/python:3.9 -> public.ecr.aws/lambda/python:3.9
            from_pattern = (
                r"^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)(?:\s+AS\s+\S+)?\s*$"
            )
            # Find all matches, ignoring case for FROM keyword
            base_images = re.findall(
                from_pattern, file_content, re.IGNORECASE | re.MULTILINE
            )
            results["base_images"] = list(set(base_images))  # Unique base images
            logger.debug(f"Found base images in {file_path}: {results['base_images']}")

            # Look for architecture-specific commands (case-insensitive)
            arch_keywords = [
                "amd64",
                "x86_64",
                "arm64",
                "aarch64",
                "arm/v",
                "graviton",
                "--platform",
            ]
            arch_commands_found = []
            for line in file_content.splitlines():
                line_lower = line.lower()
                for keyword in arch_keywords:
                    if keyword in line_lower:
                        arch_commands_found.append(line.strip())
                        break  # Found a keyword in this line, move to next line
            if arch_commands_found:
                results["arch_commands"] = arch_commands_found
                logger.debug(
                    f"Found architecture commands in {file_path}: {arch_commands_found}"
                )

        except Exception as e:
            logger.error(f"Error parsing Dockerfile {file_path}: {e}", exc_info=True)
            # Return empty results on error
            return {"base_images": [], "arch_commands": []}

        return results

    def aggregate_results(
        self, analysis_outputs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregates base image findings from multiple Dockerfile analyses.

        Args:
            analysis_outputs: A list of dictionaries, where each dictionary is the
                              output of the `analyze` method for a single Dockerfile,
                              including the 'file' path.
                              Example: [{'file': 'Dockerfile', 'analysis': {'base_images': ['python:3.9'], 'arch_commands': []}}, ...]

        Returns:
            A dictionary containing:
            - 'results': List of compatibility checks for each unique base image found.
            - 'recommendations': List of suggested actions (e.g., add platform spec).
            - 'reasoning': List of explanations for the compatibility status of each image.
        """
        aggregated_results = []
        recommendations = []
        reasoning = []
        processed_images = set()  # Track processed images to avoid duplicates

        logger.info(
            f"Aggregating Docker analysis results from {len(analysis_outputs)} files."
        )

        for output in analysis_outputs:
            file_path = output.get("file", "unknown_file")
            base_images_in_file = output.get("analysis", {}).get("base_images", [])

            for base_image in base_images_in_file:
                # Normalize image name (e.g., remove tags for general check? For now, check full name)
                image_key = base_image  # Use full image name as key for now

                if image_key not in processed_images:
                    processed_images.add(image_key)
                    logger.debug(
                        f"Checking compatibility for base image: {base_image} (found in {file_path})"
                    )

                    compatibility = self._is_docker_image_arm_compatible(base_image)
                    compatibility["file"] = file_path  # Add file path where found
                    # Add the image name itself to the result for clarity
                    compatibility["image"] = base_image

                    aggregated_results.append(compatibility)

                    # Generate reasoning and recommendations
                    reason_msg = ""
                    if compatibility.get("already_arm"):
                        reason_msg = f"Docker base image `{base_image}` explicitly targets ARM64 and is compatible."
                    elif compatibility.get("compatible") is False:
                        reason_msg = f"Docker base image `{base_image}` (in `{file_path}`) explicitly targets x86/amd64 and is incompatible with ARM64. Reason: {compatibility.get('reason', '')}"
                        recommendations.append(
                            f"Change base image `{base_image}` to an ARM64 compatible version or multi-arch tag in `{file_path}`."
                        )
                    elif compatibility.get("compatible") is True:
                        reason_msg = f"Docker base image `{base_image}` (in `{file_path}`) likely supports ARM64 (multi-arch image)."
                        if compatibility.get("suggestion"):
                            reason_msg += f" Suggestion: {compatibility['suggestion']}."
                            recommendations.append(
                                f"{compatibility['suggestion']} in `{file_path}`."
                            )
                        else:
                            reason_msg += " Explicit platform specification (`--platform=linux/arm64`) is recommended for clarity and consistency."
                            recommendations.append(
                                f"Consider adding `--platform=linux/arm64` when using `{base_image}` in `{file_path}`."
                            )
                    else:  # compatible == 'unknown'
                        reason_msg = f"Docker base image `{base_image}` (in `{file_path}`) has unknown ARM64 compatibility. Reason: {compatibility.get('reason', 'Manual verification needed')}."
                        recommendations.append(
                            f"Manually verify if `{base_image}` has ARM64 support or a multi-arch tag available, used in `{file_path}`."
                        )

                    if reason_msg:
                        reasoning.append(reason_msg)

        # De-duplicate recommendations
        unique_recommendations = sorted(list(set(recommendations)))

        logger.info(
            f"Finished aggregating Docker results. Found {len(aggregated_results)} unique base images."
        )
        return {
            "results": aggregated_results,  # Renamed from 'docker_images' for clarity
            "recommendations": unique_recommendations,
            "reasoning": reasoning,
        }

    def _is_docker_image_arm_compatible(self, base_image: str) -> Dict[str, Any]:
        """
        Checks if a Docker base image string indicates ARM compatibility.
        (Internal helper method)

        Args:
            base_image: The base image string (e.g., "python:3.9-slim", "arm64v8/ubuntu").

        Returns:
            A dictionary indicating compatibility status.
        """
        image_lower = base_image.lower()

        # --- Explicit Architecture Checks ---
        # Explicitly ARM
        if (
            "arm64" in image_lower
            or "aarch64" in image_lower
            or "arm/v8" in image_lower
            or image_lower.startswith("arm64v8/")
        ):
            return {"compatible": True, "already_arm": True}
        # Explicitly other ARM variants (might need specific handling later)
        elif "arm/v7" in image_lower or "arm32" in image_lower:
            return {
                "compatible": "partial",
                "reason": "Image targets older ARMv7/32-bit architecture. May work, but ARM64/v8 is preferred.",
            }
        # Explicitly x86/amd64
        elif (
            "amd64" in image_lower
            or "x86_64" in image_lower
            or image_lower.startswith("amd64/")
        ):
            return {
                "compatible": False,
                "reason": "Image explicitly targets x86/amd64 architecture.",
            }

        # --- Common Multi-Arch Image Heuristics ---
        # Strip tag/digest for checking common names
        image_name_only = image_lower.split(":")[0].split("@")[0]

        # Common official images known to be multi-arch
        common_multi_arch = [
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
            "openjdk",
            "ruby",
            "php",
            "httpd",
            "busybox",
            "buildpack-deps",
        ]
        # Check if the base name (without tag/registry) matches common ones
        base_name_parts = image_name_only.split("/")
        simple_name = base_name_parts[
            -1
        ]  # Get the last part (e.g., 'python' from 'library/python')

        if simple_name in common_multi_arch:
            # Check if it's likely an official image (no registry or 'library/')
            is_likely_official = len(base_name_parts) == 1 or (
                len(base_name_parts) == 2 and base_name_parts[0] == "library"
            )
            if is_likely_official:
                return {
                    "compatible": True,
                    "suggestion": f"Add platform specification: `--platform=linux/arm64` for `{base_image}`",
                    "reason": "Common official image, likely multi-arch.",
                }
            else:
                # It uses a common name but from a different registry/namespace
                return {
                    "compatible": "unknown",
                    "reason": f"Image name '{simple_name}' is common, but source ('{image_name_only}') requires verification for multi-arch support.",
                }

        # --- AWS Public ECR Images ---
        if "public.ecr.aws" in image_name_only:
            # Many AWS public images are multi-arch, but not all. Mark as likely compatible but suggest verification.
            return {
                "compatible": True,  # Optimistic assumption for public ECR
                "suggestion": f"Verify multi-arch support and consider adding `--platform=linux/arm64` for `{base_image}`",
                "reason": "AWS Public ECR image, often multi-arch.",
            }

        # --- Default Unknown ---
        logger.debug(
            f"No specific ARM compatibility rule matched for image: {base_image}. Marking as unknown."
        )
        return {
            "compatible": "unknown",
            "reason": "Image source and architecture not recognized. Manual verification needed.",
        }

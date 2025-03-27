# arm_compatibility.py

import os, sys
import re
import json
import logging

# Adjust path if necessary for imports, depending on execution context
# Ensure helpers and analyze_tools are importable

from helpers.github_api import (
    get_repository_info,
    get_repository_tree,
    get_file_content,
)
from helpers.file_analyzer import (
    extract_instance_types_from_terraform_file,
    parse_dockerfile_content,
    extract_dependencies,
)
from analyze_tools import check_arm_compatibility
from config import ENABLED_ANALYZERS  # Removed ENABLE_LLM as it wasn't used here


logger = logging.getLogger()

# Mapping from analyzer names to file patterns and analysis functions
# Moved here for clarity within this module's context
FILE_TYPE_ANALYZERS = {
    "terraform": {
        "patterns": [r"\.tf$"],
        "analysis_key": "terraform_analysis",
        "analyzer": extract_instance_types_from_terraform_file,
    },
    "docker": {
        "patterns": [
            r"Dockerfile(\.\w+)?$",
            r"/Dockerfile$",
        ],  # Allow Dockerfile.dev etc.
        "analysis_key": "dockerfile_analysis",
        "analyzer": parse_dockerfile_content,
    },
    "dependency": {
        "patterns": [r"requirements\.txt$", r"package\.json$"],
        "analysis_key": "dependency_analysis",
        "analyzer": extract_dependencies,  # This needs the file_type arg below
    },
}


def extract_repo_info(repo_url):
    """GitHub URL에서 소유자와 저장소 이름을 추출합니다."""
    # Allow optional .git suffix and trailing slash
    pattern = r"https?://github\.com/([^/]+)/([^/\s]+?)(?:\.git)?/?$"
    match = re.match(pattern, repo_url.strip())
    if not match:
        raise ValueError(f"Invalid GitHub repository URL format: {repo_url}")
    return match.group(1), match.group(2)


def check_compatibility(github_url):
    """
    Analyzes a GitHub repository for ARM compatibility based on enabled analyzers.

    Args:
        github_url: The URL of the GitHub repository.

    Returns:
        A dictionary containing either:
        - {'repository': str, 'compatibility_result': dict} on success.
        - {'repository': str, 'error': str} on failure during analysis.
    """
    owner = None
    repo = None
    try:
        owner, repo = extract_repo_info(github_url)
        logger.info(f"Starting ARM compatibility analysis for: {owner}/{repo}")

        repo_info = get_repository_info(owner, repo)
        if (
            not repo_info
        ):  # Handle case where repo doesn't exist or token lacks permissions
            raise ValueError(
                f"Could not retrieve repository info for {owner}/{repo}. Check URL and permissions."
            )
        default_branch = repo_info.get("default_branch", "main")
        logger.info(f"Using default branch: {default_branch}")

        tree = get_repository_tree(owner, repo, default_branch)
        if not tree or "tree" not in tree:
            # Handle empty repo or error fetching tree
            logger.warning(
                f"Could not retrieve file tree for {owner}/{repo}. It might be empty or inaccessible."
            )
            # Return a specific result indicating no files analyzed?
            # For now, let check_arm_compatibility handle empty results.
            tree = {"tree": []}

        # Initialize results structure based on *enabled* analyzers
        analysis_results = {}
        enabled_file_categories = {}
        logger.info(
            f"Enabled analyzers: {[name for name, enabled in ENABLED_ANALYZERS.items() if enabled]}"
        )

        for analyzer_name, enabled in ENABLED_ANALYZERS.items():
            if enabled and analyzer_name in FILE_TYPE_ANALYZERS:
                config = FILE_TYPE_ANALYZERS[analyzer_name]
                analysis_results[config["analysis_key"]] = []
                enabled_file_categories[analyzer_name] = {"config": config, "files": []}

        # Identify relevant files based *only* on enabled analyzers
        for item in tree.get("tree", []):
            if item.get("type") == "blob":
                path = item["path"]
                for analyzer_name, category_data in enabled_file_categories.items():
                    for pattern in category_data["config"]["patterns"]:
                        if re.search(
                            pattern, path, re.IGNORECASE
                        ):  # Ignore case for robustness
                            category_data["files"].append(path)
                            logger.debug(
                                f"Found relevant file '{path}' for analyzer '{analyzer_name}'"
                            )
                            break  # File matches this category, move to next file

        # Analyze the identified files
        total_files_analyzed = 0
        for analyzer_name, category_data in enabled_file_categories.items():
            config = category_data["config"]
            analysis_key = config["analysis_key"]
            analyzer_func = config["analyzer"]

            logger.info(
                f"Analyzing {len(category_data['files'])} files for '{analyzer_name}'..."
            )
            for file_path in category_data["files"]:
                try:
                    content = get_file_content(owner, repo, file_path, default_branch)
                    if content is not None:  # Ensure content was fetched
                        total_files_analyzed += 1
                        analysis_output = None
                        # Special handling for dependency analyzer needing file type
                        if analyzer_name == "dependency":
                            file_type = (
                                "txt"
                                if file_path.lower().endswith("requirements.txt")
                                else (
                                    "json"
                                    if file_path.lower().endswith("package.json")
                                    else None
                                )
                            )
                            if file_type:
                                analysis_output = analyzer_func(content, file_type)
                        else:
                            analysis_output = analyzer_func(content)

                        if analysis_output:
                            # Include raw content only for dependency analysis where it's needed downstream
                            result_entry = {
                                "file": file_path,
                                "analysis": analysis_output,
                            }
                            if analyzer_name == "dependency":
                                result_entry["content"] = (
                                    content  # Keep content for pipgrip etc.
                                )
                            analysis_results[analysis_key].append(result_entry)

                    else:
                        logger.warning(f"Could not get content for file: {file_path}")
                except Exception as file_error:
                    logger.error(
                        f"Error analyzing file {file_path} with {analyzer_name}: {file_error}"
                    )
                    # Optionally record this file error in the results

            logger.info(f"Finished analyzing for '{analyzer_name}'.")

        if total_files_analyzed == 0:
            logger.warning(
                f"No relevant files found or analyzed for enabled analyzers in {owner}/{repo}."
            )
            # Consider returning a specific status or letting check_arm_compatibility report 'unknown'

        # Perform the overall compatibility check using the collected results
        logger.info("Running final compatibility check based on collected analysis...")
        compatibility_result = check_arm_compatibility(analysis_results)
        logger.info(
            f"Overall compatibility assessment: {compatibility_result.get('overall_compatibility')}"
        )

        return {
            "repository": f"{owner}/{repo}",  # Return owner/repo for consistency
            "github_url": github_url,  # Also return original URL
            "compatibility_result": compatibility_result,
        }

    except Exception as e:
        logger.exception(
            f"Error during ARM compatibility check for {github_url}: {str(e)}"
        )
        # Return a structured error
        return {
            "repository": (
                f"{owner}/{repo}" if owner else github_url
            ),  # Use best available identifier
            "github_url": github_url,
            "error": str(e),
        }

import os
import re
from github_api import get_repository_info, get_repository_tree, get_file_content
from file_analyzer import (
    analyze_terraform_file,
    analyze_dockerfile,
    analyze_dependencies,
)
from compatibility_checker import check_arm_compatibility
from llm_agent import get_llm_assessment
from config import ENABLE_LLM


def extract_repo_info(repo_url):
    """Extract owner and repo from GitHub URL."""
    pattern = r"https?://github\.com/([^/]+)/([^/]+)"
    match = re.match(pattern, repo_url)
    if not match:
        raise ValueError("Invalid GitHub repository URL")
    return match.group(1), match.group(2)


def analyze_repository(repo_url):
    """Main function to analyze a repository for ARM64 compatibility."""
    # Extract repository information
    owner, repo = extract_repo_info(repo_url)
    print(f"Analyzing repository: {owner}/{repo}")

    # Get repository metadata
    repo_info = get_repository_info(owner, repo)
    default_branch = repo_info.get("default_branch", "main")

    # Get file tree
    tree = get_repository_tree(owner, repo, default_branch)

    # Initialize data containers
    terraform_files = []
    dockerfiles = []
    dependency_files = []

    # Identify relevant files
    for item in tree.get("tree", []):
        if item["type"] == "blob":
            path = item["path"]
            if path.endswith(".tf"):
                terraform_files.append(path)
            elif path.endswith("Dockerfile") or "/Dockerfile" in path:
                dockerfiles.append(path)
            elif any(
                path.endswith(dep)
                for dep in [
                    "requirements.txt",
                    "package.json",
                    "pom.xml",
                    "build.gradle",
                ]
            ):
                dependency_files.append(path)

    # Analysis results
    results = {
        "terraform_analysis": [],
        "dockerfile_analysis": [],
        "dependency_analysis": [],
    }

    # Analyze Terraform files
    for tf_file in terraform_files:
        content = get_file_content(owner, repo, tf_file)
        if content:
            analysis = analyze_terraform_file(content)
            if analysis:
                results["terraform_analysis"].append(
                    {"file": tf_file, "analysis": analysis}
                )

    # Analyze Dockerfiles
    for dockerfile in dockerfiles:
        content = get_file_content(owner, repo, dockerfile)
        if content:
            analysis = analyze_dockerfile(content)
            if analysis:
                results["dockerfile_analysis"].append(
                    {"file": dockerfile, "analysis": analysis}
                )

    # Analyze dependencies
    for dep_file in dependency_files:
        content = get_file_content(owner, repo, dep_file)
        if content:
            file_type = dep_file.split(".")[-1] if "." in dep_file else "txt"
            analysis = analyze_dependencies(content, file_type)
            if analysis:
                results["dependency_analysis"].append(
                    {"file": dep_file, "analysis": analysis}
                )

    # Check compatibility
    compatibility_result = check_arm_compatibility(results)

    # Get LLM assessment if enabled
    if ENABLE_LLM:
        llm_assessment = get_llm_assessment(compatibility_result)
    else:
        llm_assessment = "LLM assessment disabled. Set ENABLE_LLM=True to enable."

    return {
        "repository": f"{owner}/{repo}",
        "compatibility_result": compatibility_result,
        "llm_assessment": llm_assessment,
    }


def lambda_handler(event, context):
    """AWS Lambda handler function."""
    repo_url = event.get("repo_url")
    if not repo_url:
        return {"statusCode": 400, "body": "Repository URL is required"}

    try:
        result = analyze_repository(repo_url)
        return {"statusCode": 200, "body": result}
    except Exception as e:
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


if __name__ == "__main__":
    # For local testing
    import sys

    if len(sys.argv) > 1:
        result = analyze_repository(sys.argv[1])
        print("\nARM64 Compatibility Analysis:")
        print(f"Repository: {result['repository']}")
        print(f"Assessment: {result['llm_assessment']}")
    else:
        print("Usage: python main.py <github_repo_url>")

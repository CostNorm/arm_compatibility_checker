import os
import re
import json
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


def save_results_to_markdown(result, output_file="result.md"):
    """Save analysis results to a markdown file."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# ARM64 호환성 분석 결과\n\n")
        f.write(f"## 저장소: {result['repository']}\n\n")

        # 호환성 결과 출력
        compatibility = result["compatibility_result"]["overall_compatibility"]
        emoji = (
            "✅"
            if compatibility == "compatible"
            else "❓" if compatibility == "unknown" else "❌"
        )
        f.write(f"## 호환성: {emoji} {compatibility}\n\n")

        # 상세 분석 결과
        f.write("## 상세 분석\n\n")
        f.write(
            f"- 인스턴스 타입: {len(result['compatibility_result'].get('instance_types', []))} 이슈\n"
        )
        f.write(
            f"- 도커 이미지: {len(result['compatibility_result'].get('docker_images', []))} 이슈\n"
        )
        f.write(
            f"- 종속성: {len(result['compatibility_result'].get('dependencies', []))} 이슈\n\n"
        )

        # 권장사항
        if result["compatibility_result"].get("recommendations"):
            f.write("## 권장사항\n\n")
            for rec in result["compatibility_result"]["recommendations"]:
                f.write(f"- {rec}\n")
            f.write("\n")

        # LLM 평가
        f.write("## LLM 평가\n\n")
        f.write(f"{result['llm_assessment']}\n")

    print(f"\n결과가 {output_file}에 저장되었습니다.")


if __name__ == "__main__":
    # For local testing
    import argparse

    parser = argparse.ArgumentParser(
        description="Check GitHub repository ARM compatibility"
    )
    parser.add_argument("--repo", required=True, help="GitHub repository URL")
    parser.add_argument("--output", default="results.json", help="Output file path")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--skip-deps", action="store_true", help="Skip dependency checks"
    )

    args = parser.parse_args()

    try:
        result = analyze_repository(args.repo)
        print("\nARM64 Compatibility Analysis:")
        print(f"Repository: {result['repository']}")

        # Print compatibility result with appropriate emoji
        compatibility = result["compatibility_result"]["overall_compatibility"]
        emoji = (
            "✅"
            if compatibility == "compatible"
            else "❓" if compatibility == "unknown" else "❌"
        )
        print(f"Compatibility: {emoji} {compatibility}")

        print(f"Assessment: {result['llm_assessment']}")

        if args.verbose:
            # Print detailed analysis results
            print("\nDetailed Analysis:")
            print(
                f"Instance Types: {len(result['compatibility_result'].get('instance_types', []))} issues"
            )
            print(
                f"Docker Images: {len(result['compatibility_result'].get('docker_images', []))} issues"
            )
            print(
                f"Dependencies: {len(result['compatibility_result'].get('dependencies', []))} issues"
            )

            # Print recommendations
            if result["compatibility_result"].get("recommendations"):
                print("\nRecommendations:")
                for rec in result["compatibility_result"].get("recommendations"):
                    print(f"- {rec}")

        # Save results to JSON if specified
        if args.output.endswith(".json"):
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to {args.output}")

        # Always save to result.md for local testing
        save_results_to_markdown(result)

    except ValueError as e:
        print(f"Error: {e}")
        parser.print_help()

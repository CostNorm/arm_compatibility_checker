import re
import json

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

# Simplified import using the new package structure
from analyze_tools import check_arm_compatibility
from llm_tools.llm_agent import get_llm_assessment
from config import ENABLE_LLM, ENABLED_ANALYZERS

# 파일 타입과 분석기 매핑 정의 - 간소화
FILE_TYPE_ANALYZERS = {
    "terraform": {
        "patterns": [r"\.tf$"],  # Terraform 파일 패턴
        "analysis_key": "terraform_analysis",
        "analyzer": extract_instance_types_from_terraform_file,
    },
    "docker": {
        "patterns": [r"Dockerfile$", r"/Dockerfile"],  # Dockerfile 패턴
        "analysis_key": "dockerfile_analysis",
        "analyzer": parse_dockerfile_content,
    },
    "dependency": {
        "patterns": [r"requirements\.txt$"],  # 의존성 파일 패턴 - Python만 유지
        "analysis_key": "dependency_analysis",
        "analyzer": extract_dependencies,
    },
}


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

    # Initialize results container
    results = {}

    # Create file categories based on enabled analyzers
    file_categories = {}

    # 활성화된 분석기에 대해서만 파일 카테고리 생성
    for analyzer_name, enabled in ENABLED_ANALYZERS.items():
        if enabled and analyzer_name in FILE_TYPE_ANALYZERS:
            file_categories[analyzer_name] = []
            # 각 분석기에 대한 분석 결과 키 초기화
            results[FILE_TYPE_ANALYZERS[analyzer_name]["analysis_key"]] = []

    # Identify relevant files based on enabled analyzers
    for item in tree.get("tree", []):
        if item["type"] == "blob":
            path = item["path"]

            # 활성화된 분석기에 대해 파일 체크
            for analyzer_name, category_info in file_categories.items():
                analyzer_config = FILE_TYPE_ANALYZERS[analyzer_name]
                for pattern in analyzer_config["patterns"]:
                    if re.search(pattern, path):
                        category_info.append(path)
                        break

    # Analyze files for each enabled analyzer
    for analyzer_name, file_paths in file_categories.items():
        analyzer_config = FILE_TYPE_ANALYZERS[analyzer_name]
        analysis_key = analyzer_config["analysis_key"]
        analyzer_func = analyzer_config["analyzer"]

        for file_path in file_paths:
            content = get_file_content(owner, repo, file_path)
            if content:
                # 의존성 분석기는 파일 타입 인자가 필요하므로 특별 처리
                if analyzer_name == "dependency":
                    # 파일 타입 처리 간소화 - txt만 처리
                    file_type = "txt"
                    analysis = analyzer_func(content, file_type)
                    if analysis:
                        results[analysis_key].append(
                            {
                                "file": file_path,
                                "analysis": analysis,
                                "content": content,
                            }
                        )
                else:
                    analysis = analyzer_func(content)
                    if analysis:
                        results[analysis_key].append(
                            {"file": file_path, "analysis": analysis}
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

        # 인스턴스 타입 및 도커 이미지 분석
        f.write(
            f"- 인스턴스 타입: {len(result['compatibility_result'].get('instance_types', []))} 이슈\n"
        )
        f.write(
            f"- 도커 이미지: {len(result['compatibility_result'].get('docker_images', []))} 이슈\n"
        )

        # 종속성 분석 상세 정보
        dependencies = result["compatibility_result"].get("dependencies", [])
        total_deps = len(dependencies)
        direct_deps = sum(1 for dep in dependencies if dep.get("direct", True))
        transitive_deps = total_deps - direct_deps
        incompatible_deps = sum(
            1 for dep in dependencies if dep.get("compatible") is False
        )

        f.write(
            f"- 종속성: {total_deps} 분석됨 ({direct_deps} 직접, {transitive_deps} 전이적), {incompatible_deps} 이슈\n\n"
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
    # Removed --skip-deps argument

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

            # Enhanced dependency info
            dependencies = result["compatibility_result"].get("dependencies", [])
            total_deps = len(dependencies)
            direct_deps = sum(1 for dep in dependencies if dep.get("direct", True))
            transitive_deps = total_deps - direct_deps
            incompatible_deps = sum(
                1 for dep in dependencies if dep.get("compatible") is False
            )

            print(
                f"Dependencies: {total_deps} analyzed ({direct_deps} direct, {transitive_deps} transitive), {incompatible_deps} issues"
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

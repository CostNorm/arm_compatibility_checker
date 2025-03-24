import os, sys
import re
import json

# 프로젝트 루트 디렉토리를 PATH에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 기존 분석 로직 임포트
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
from config import ENABLE_LLM, ENABLED_ANALYZERS
from .notify import notify_arm_suggestions


def extract_repo_info(repo_url):
    """GitHub URL에서 소유자와 저장소 이름을 추출합니다."""
    pattern = r"https?://github\.com/([^/]+)/([^/]+)"
    match = re.match(pattern, repo_url)
    if not match:
        raise ValueError("유효하지 않은 GitHub 저장소 URL입니다")
    return match.group(1), match.group(2)


def check_compatibility(github_url):
    """
    GitHub 저장소의 ARM 호환성을 확인합니다.

    Args:
        github_url: GitHub 저장소 URL

    Returns:
        dict: 호환성 검사 결과와 제안사항
    """
    try:
        # 저장소 정보 추출
        owner, repo = extract_repo_info(github_url)
        print(f"저장소 분석 중: {owner}/{repo}")

        # 저장소 메타데이터 가져오기
        repo_info = get_repository_info(owner, repo)
        default_branch = repo_info.get("default_branch", "main")

        # 파일 트리 가져오기
        tree = get_repository_tree(owner, repo, default_branch)

        print(f"tree: {tree}")

        # 결과 컨테이너 초기화
        results = {}

        # 활성화된 분석기에 대한 파일 카테고리 생성
        file_categories = {}

        # 메인 모듈의 FILE_TYPE_ANALYZERS와 동일한 값 사용
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
                "patterns": [
                    r"requirements\.txt$",
                    r"package\.json$",
                ],  # 의존성 파일 패턴
                "analysis_key": "dependency_analysis",
                "analyzer": extract_dependencies,
            },
        }

        # 활성화된 분석기에 대해서만 파일 카테고리 생성
        print(f"ENABLED_ANALYZERS: {ENABLED_ANALYZERS}")
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
                        # Determine file type
                        if file_path.endswith("requirements.txt"):
                            file_type = "txt"
                        elif file_path.endswith("package.json"):
                            file_type = "json"
                        else:
                            continue

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

        # ARM 호환성 검증
        compatibility_result = check_arm_compatibility(results)
        print(f"results: {results}")
        print(f"compatibility_result: {compatibility_result}")

        # 결과에서 제안사항 목록 생성
        suggestions = []

        # 호환성 결과에 따른 아이콘 결정
        compatibility = compatibility_result["overall_compatibility"]
        icon = (
            "✅"
            if compatibility == "compatible"
            else "❓" if compatibility == "unknown" else "❌"
        )

        # 종합 호환성 메시지
        summary = f"{icon} *`{github_url}`* 저장소의 ARM 호환성: *{compatibility}*"
        suggestions.append(summary)

        # 상세 분석 정보 추가
        suggestions.append("\n*상세 분석 결과:*")

        # 인스턴스 유형 문제
        instance_types = compatibility_result.get("instance_types", [])
        if instance_types:
            suggestions.append(f"• 인스턴스 유형 이슈: {len(instance_types)}개")
            for issue in instance_types:
                suggestions.append(
                    f"  - {issue.get('file_path')}: {issue.get('instance_type')} ({issue.get('reason')})"
                )

        # 도커 이미지 문제
        docker_images = compatibility_result.get("docker_images", [])
        if docker_images:
            suggestions.append(f"• 도커 이미지 이슈: {len(docker_images)}개")
            for issue in docker_images:
                suggestions.append(
                    f"  - {issue.get('file_path')}: {issue.get('image')} ({issue.get('reason')})"
                )

        # 종속성 문제
        dependencies = compatibility_result.get("dependencies", [])
        incompatible_deps = [
            dep for dep in dependencies if dep.get("compatible") is False
        ]
        if incompatible_deps:
            suggestions.append(f"• 종속성 이슈: {len(incompatible_deps)}개")
            for issue in incompatible_deps:
                suggestions.append(f"  - {issue.get('name')}: {issue.get('reason')}")

        # 권장사항 추가
        recommendations = compatibility_result.get("recommendations", [])
        if recommendations:
            suggestions.append("\n*권장사항:*")
            for rec in recommendations:
                suggestions.append(f"• {rec}")

        return {
            "repository": f"{owner}/{repo}",
            "compatibility_result": compatibility_result,
            "suggestions": suggestions,
        }
    except Exception as e:
        print(f"ARM 호환성 검사 중 오류 발생: {str(e)}")

        # 오류 메시지 생성
        error_message = f"❌ 오류 발생: {str(e)}"
        error_suggestions = [error_message]

        # Slack으로 오류 알림 전송 (환경 변수에서 Webhook URL 또는 채널 가져오기)
        slack_channel = os.environ.get("SLACK_NOTIFICATION_CHANNEL")
        if slack_channel:
            notify_arm_suggestions(slack_channel, error_suggestions)

        return {
            "repository": github_url,
            "error": str(e),
            "suggestions": error_suggestions,
        }

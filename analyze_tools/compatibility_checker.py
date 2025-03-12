from analyze_tools.terraform_tools.terraform_analyzer import (
    analyze_terraform_compatibility,
)
from analyze_tools.docker_tools.docker_analyzer import (
    analyze_docker_compatibility,
)
from analyze_tools.dependency_tools.dependency_resolver import (
    analyze_dependency_compatibility,
)
from config import ENABLED_ANALYZERS


def check_arm_compatibility(analysis_results):
    """
    Check ARM64 compatibility based on the analysis results from enabled analyzers.
    Dynamically includes/excludes analyzers based on configuration.
    """
    compatibility_result = {
        "overall_compatibility": None,
        "instance_types": [],
        "docker_images": [],
        "dependencies": [],
        "recommendations": [],
        "context": {  # Add context information for LLM
            "analysis_summary": {
                "terraform_files_analyzed": len(
                    analysis_results.get("terraform_analysis", [])
                ),
                "dockerfile_files_analyzed": len(
                    analysis_results.get("dockerfile_analysis", [])
                ),
                "dependency_files_analyzed": len(
                    analysis_results.get("dependency_analysis", [])
                ),
            },
            "reasoning": [],
            "process_description": "ARM compatibility was analyzed by examining selected architecture-specific components.",
            "enabled_analyzers": [
                name for name, enabled in ENABLED_ANALYZERS.items() if enabled
            ],
        },
    }

    # Dictionary of available analyzers
    analyzers = {
        "terraform": {
            "enabled": ENABLED_ANALYZERS.get("terraform", True),
            "function": analyze_terraform_compatibility,
            "input_key": "terraform_analysis",
            "output_key": "instance_types",
        },
        "docker": {
            "enabled": ENABLED_ANALYZERS.get("docker", True),
            "function": analyze_docker_compatibility,
            "input_key": "dockerfile_analysis",
            "output_key": "docker_images",
        },
        "dependency": {
            "enabled": ENABLED_ANALYZERS.get("dependency", True),
            "function": analyze_dependency_compatibility,
            "input_key": "dependency_analysis",
            "output_key": "dependencies",
        },
    }

    # Dynamically run enabled analyzers
    for name, analyzer_config in analyzers.items():
        if analyzer_config["enabled"]:
            analyzer_results = analyzer_config["function"](
                analysis_results.get(analyzer_config["input_key"], [])
            )
            compatibility_result[analyzer_config["output_key"]] = analyzer_results[
                analyzer_config["output_key"]
            ]
            compatibility_result["recommendations"].extend(
                analyzer_results["recommendations"]
            )
            compatibility_result["context"]["reasoning"].extend(
                analyzer_results["reasoning"]
            )

    # Determine overall compatibility
    if (
        not compatibility_result["instance_types"]
        and not compatibility_result["docker_images"]
        and not compatibility_result["dependencies"]
    ):
        compatibility_result["overall_compatibility"] = "unknown"
        compatibility_result["recommendations"].append(
            "No clear architecture-specific elements found. Manual verification recommended."
        )
        compatibility_result["context"]["reasoning"].append(
            "No architecture-specific elements were identified in the analysis, making compatibility assessment uncertain."
        )
    else:
        # Check if there are any incompatible elements
        has_incompatible = any(
            item.get("compatible") is False
            for category in ["instance_types", "docker_images", "dependencies"]
            for item in compatibility_result[category]
        )

        if has_incompatible:
            compatibility_result["overall_compatibility"] = "incompatible"
            compatibility_result["context"]["reasoning"].append(
                "Repository is marked as incompatible because one or more components explicitly conflict with ARM64 architecture."
            )
        else:
            compatibility_result["overall_compatibility"] = "compatible"
            compatibility_result["context"]["reasoning"].append(
                "Repository is likely compatible with ARM64 as no explicitly incompatible elements were found."
            )

    # Add summary statistics to context
    compatibility_result["context"]["statistics"] = {
        "incompatible_items": sum(
            1
            for item in compatibility_result["instance_types"]
            + compatibility_result["docker_images"]
            + compatibility_result["dependencies"]
            if item.get("compatible") is False
        ),
        "compatible_items": sum(
            1
            for item in compatibility_result["instance_types"]
            + compatibility_result["docker_images"]
            + compatibility_result["dependencies"]
            if item.get("compatible") is True
        ),
        "unknown_items": sum(
            1
            for item in compatibility_result["instance_types"]
            + compatibility_result["docker_images"]
            + compatibility_result["dependencies"]
            if item.get("compatible") == "unknown"
        ),
        "total_recommendations": len(compatibility_result["recommendations"]),
    }

    return compatibility_result

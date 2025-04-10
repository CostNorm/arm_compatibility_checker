# Refactoring Plan for ARM Compatibility Checker

**1. Goal:** Refactor the ARM Compatibility Bot Lambda function to improve modularity, readability, testability, and extensibility.

**2. Proposed Directory Structure:**

```
alpha/lambdas/ARMCompatibilityBot_lambda/src/
├── config.py                 # Centralized configuration
├── lambda_function.py        # Lambda entry point
├── sqs_processor.py          # SQS message parsing (mostly unchanged)
│
├── core/                     # Core interfaces and base classes
│   ├── __init__.py
│   └── interfaces.py         # Define Analyzer, DependencyChecker interfaces
│
├── services/                 # External service interactions
│   ├── __init__.py
│   ├── github_service.py     # Handles all GitHub API interactions
│   └── llm_service.py        # Handles LLM interaction (Bedrock/Gemini)
│
├── analyzers/                # Different analysis types
│   ├── __init__.py
│   ├── base_analyzer.py      # Abstract base class implementing core.interfaces.Analyzer
│   ├── terraform_analyzer.py # Terraform-specific analysis logic
│   ├── docker_analyzer.py    # Dockerfile-specific analysis logic
│   └── dependency_analyzer/  # Dependency analysis module
│       ├── __init__.py
│       ├── base_checker.py   # Abstract base class implementing core.interfaces.DependencyChecker
│       ├── manager.py        # Manages different dependency checkers (Python, JS, etc.)
│       ├── python_checker.py # Python-specific dependency checking (uses pypi_api, wheel_test_api)
│       └── js_checker.py     # JavaScript-specific dependency checking
│
├── analysis_orchestrator.py  # Coordinates the overall analysis process
│
└── slack/                    # Slack-specific logic
    ├── __init__.py
    ├── handler.py            # Handles Slack event dispatching
    └── utils.py              # Slack message formatting utilities
```

**3. Core Interfaces (`core/interfaces.py`):**

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class Analyzer(ABC):
    """Interface for analyzing a specific aspect (Terraform, Docker, Dependencies)."""

    @abstractmethod
    def analyze(self, file_content: str, file_path: str) -> Dict[str, Any]:
        """Analyzes the content of a single file."""
        pass

    @abstractmethod
    def aggregate_results(self, analysis_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregates results from multiple file analyses for this type."""
        pass

    @property
    @abstractmethod
    def relevant_file_patterns(self) -> List[str]:
        """Regex patterns for files relevant to this analyzer."""
        pass

    @property
    @abstractmethod
    def analysis_key(self) -> str:
        """Key used in the final results dictionary for this analyzer's output."""
        pass


class DependencyChecker(ABC):
    """Interface for checking compatibility of dependencies for a specific ecosystem."""

    @abstractmethod
    def check_compatibility(self, dependency_info: Dict[str, Any]) -> Dict[str, Any]:
        """Checks the compatibility of a single dependency."""
        pass

    @abstractmethod
    def parse_dependencies(self, file_content: str, file_path: str) -> List[Dict[str, Any]]:
        """Parses dependencies from a manifest file."""
        pass
```

**4. Refactoring Steps & Module Responsibilities:**

- **`config.py`:** Keep as the central place for environment variables and flags (GITHUB_TOKEN, LLM settings, ENABLED_ANALYZERS).
- **`lambda_function.py`:** Simplify significantly. Its main job is to parse the SQS message (using `sqs_processor`), instantiate the `SlackHandler`, and pass the event to it.
- **`sqs_processor.py`:** Remains largely unchanged, focused solely on parsing the SQS message body.
- **`core/interfaces.py`:** Define the `Analyzer` and `DependencyChecker` abstract base classes/interfaces as shown above.
- **`services/github_service.py`:**
  - Move all functions from `helpers/github_api.py` here.
  - Encapsulate GitHub interactions (fetching repo info, tree, file content).
  - Handle authentication and potential API errors gracefully.
- **`services/llm_service.py`:**
  - Move logic from `slack_bot/llm_service.py`.
  - Focus solely on interacting with the LLM (Bedrock/Gemini) via Langchain.
  - Takes structured compatibility data and returns a formatted string summary.
- **`analyzers/base_analyzer.py`:** Implement the `Analyzer` interface. Concrete analyzers will inherit from this.
- **`analyzers/terraform_analyzer.py`:**
  - Inherit from `BaseAnalyzer`.
  - Implement `analyze` using logic from `helpers/file_analyzer.extract_instance_types_from_terraform_file`.
  - Implement `aggregate_results` using logic from `analyze_tools/terraform_tools/terraform_analyzer.analyze_terraform_compatibility`.
  - Define `relevant_file_patterns` (e.g., `[r"\.tf$"]`) and `analysis_key` (`"instance_types"`).
  - Keep `is_instance_type_arm_compatible` as a helper function within this module or a sub-module.
- **`analyzers/docker_analyzer.py`:**
  - Inherit from `BaseAnalyzer`.
  - Implement `analyze` using logic from `helpers/file_analyzer.parse_dockerfile_content`.
  - Implement `aggregate_results` using logic from `analyze_tools/docker_tools/docker_analyzer.analyze_docker_compatibility`.
  - Define `relevant_file_patterns` (e.g., `[r"Dockerfile(\.\w+)?$", r"/Dockerfile$"]`) and `analysis_key` (`"docker_images"`).
  - Keep `is_docker_image_arm_compatible` as a helper function.
- **`analyzers/dependency_analyzer/base_checker.py`:** Implement the `DependencyChecker` interface. Concrete checkers (Python, JS) will inherit.
- **`analyzers/dependency_analyzer/python_checker.py`:**
  - Inherit from `BaseDependencyChecker`.
  - Implement `parse_dependencies` using logic from `helpers/file_analyzer.extract_dependencies` (for requirements.txt).
  - Implement `check_compatibility` using the consolidated logic from `analyze_tools/dependency_tools/python/python_package_compatibility.py`, which calls `pypi_api` and `wheel_test_api`.
  - Move `pypi_api.py` and `wheel_test_api.py` logic into helper functions or classes within this module or a sub-module (e.g., `analyzers/dependency_analyzer/python_helpers/`). Keep `pip_source_build.py` here if needed for future use.
- **`analyzers/dependency_analyzer/js_checker.py`:**
  - Inherit from `BaseDependencyChecker`.
  - Implement `parse_dependencies` using logic from `helpers/file_analyzer.extract_dependencies` (for package.json).
  - Implement `check_compatibility` using logic from `analyze_tools/dependency_tools/js_compatibility.py`.
- **`analyzers/dependency_analyzer/manager.py`:**
  - This acts as the main entry point for dependency analysis.
  - Inherits from `BaseAnalyzer`.
  - `relevant_file_patterns` will include patterns for `requirements.txt`, `package.json`, etc.
  - `analysis_key` will be `"dependencies"`.
  - The `analyze` method determines the file type (`requirements.txt` vs `package.json`) and calls the appropriate `parse_dependencies` method from `python_checker` or `js_checker`.
  - The `aggregate_results` method iterates through parsed dependencies, calls the appropriate `check_compatibility` method (`python_checker` or `js_checker`), and aggregates the final dependency results and recommendations (similar to the old `dependency_analyzer.analyze_dependency_compatibility`).
- **`analysis_orchestrator.py`:**
  - Replaces the core logic of `slack_bot/arm_compatibility.py`.
  - Takes owner/repo as input.
  - Uses `GithubService` to fetch the file tree.
  - Instantiates enabled `Analyzer`s based on `config.ENABLED_ANALYZERS`.
  - Identifies relevant files for each enabled analyzer.
  - Fetches content for relevant files using `GithubService`.
  - Calls the `analyze` method for each relevant file on the corresponding analyzer.
  - Calls the `aggregate_results` method for each analyzer.
  - Combines aggregated results into the final `compatibility_result` structure (similar to `analyze_tools/compatibility_checker.py`). Includes context like enabled analyzers.
  - Returns the final `compatibility_result` dictionary or raises errors.
- **`slack/handler.py`:**
  - Replaces `slack_bot/slack_handler.py`.
  - Receives parsed Slack body from `lambda_function`.
  - Handles event dispatching (`app_mention`, `block_actions`, etc.).
  - For analysis requests (`app_mention` with "analyze"):
    - Extracts the GitHub URL.
    - Calls `SlackUtils.send_ack_message`.
    - Calls the `AnalysisOrchestrator` to perform the analysis.
    - If LLM is enabled, calls `LLMService.summarize`.
    - Calls `SlackUtils` to format the final result (LLM summary or structured data) or error message.
    - Calls `SlackUtils.send_result_message`.
- **`slack/utils.py`:**
  - Replaces `slack_bot/slack_utils.py`.
  - Contains only functions for formatting Slack Block Kit messages (ack, error, help, results, LLM summary).
  - Includes the `send_slack_block_message` and `update_slack_message` helpers.

**5. Mermaid Diagram:**

```mermaid
graph TD
    subgraph Lambda Entry
        SQS[SQS Event] --> Lambda[lambda_function.py]
        Lambda --> SQSProc[sqs_processor.py]
        SQSProc --> SlackBody[Parsed Slack Body]
        Lambda --> SlackHandler[slack.handler.py]
        SlackBody --> SlackHandler
    end

    subgraph Slack Interaction
        SlackHandler -- analyze request --> Orchestrator[analysis_orchestrator.py]
        SlackHandler -- format/send --> SlackUtils[slack.utils.py]
        SlackUtils -- API Call --> SlackAPI[(Slack API)]
    end

    subgraph Analysis Core
        Orchestrator -- uses --> Config[config.py]
        Orchestrator -- uses --> GithubService[services.github_service.py]
        Orchestrator -- uses --> Analyzers(Enabled Analyzers)

        subgraph Analyzers
            Analyzers -- include --> Terraform[analyzers.terraform_analyzer.py]
            Analyzers -- include --> Docker[analyzers.docker_analyzer.py]
            Analyzers -- include --> DepManager[analyzers.dependency_analyzer.manager.py]
        end

        DepManager -- uses --> PyChecker[analyzers.dependency_analyzer.python_checker.py]
        DepManager -- uses --> JSChecker[analyzers.dependency_analyzer.js_checker.py]
        PyChecker -- uses --> PyHelpers(PyPI/Wheel APIs)

        Analyzers -- implement --> CoreInterfaces[core.interfaces.py]
        DepManager -- implement --> CoreInterfaces
        PyChecker -- implement --> CoreInterfaces
        JSChecker -- implement --> CoreInterfaces

        GithubService -- API Call --> GitHubAPI[(GitHub API)]
    end

    subgraph Summarization
        Orchestrator --> CompatibilityResult[Final Result Dict]
        SlackHandler -- sends result to --> LLMService[services.llm_service.py]
        LLMService -- API Call --> LLM_API[(Bedrock/LLM API)]
        LLMService --> LLMSummary[Formatted Summary]
        LLMSummary --> SlackHandler
    end

    CompatibilityResult --> SlackHandler
```

**6. Next Steps:**

- **Review:** Please review this proposed structure and refactoring plan. Does it align with your vision for a more modular and extensible system? Are there any parts that seem unclear or could be improved?
- **Approval:** Once you're satisfied with the plan, please confirm.
- **Save Plan (Optional):** Would you like me to write this plan (including the structure and Mermaid diagram) to a Markdown file (e.g., `refactoring_plan.md`) in the workspace?
- **Implementation:** After approval, I can request to switch to 'code' mode to start implementing these changes step-by-step.

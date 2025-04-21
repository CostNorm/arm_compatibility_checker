# ARM Compatibility Bot (for Slack)

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) <!-- Optional license badge -->

## README Language Selection

- [Korean Translation](readme.ko.md)
- [English](readme.md)

## Overview

The ARM Compatibility Bot is a Slack application designed to help developers and operations teams assess the ARM64 compatibility of their GitHub repositories. This is particularly useful when planning migrations to ARM-based compute platforms like AWS Graviton processors.

The bot listens for commands in Slack, fetches the specified GitHub repository, analyzes various configuration and dependency files, and reports potential compatibility issues directly back into the Slack thread. It can optionally leverage AWS Bedrock Language Models (LLMs) to provide a more human-readable summary of the findings.

## Features

- **Slack Integration:** Interact with the bot directly within Slack using mentions (`@ARMCompatBot analyze ...`).
- **GitHub Repository Analysis:** Fetches repository contents via the GitHub API.
- **Modular Analyzers:** Supports analysis of:
  - **Terraform (`.tf`):** Checks EC2 instance types and suggests ARM equivalents (e.g., Graviton `t4g`, `m6g`, `c7g`, etc.).
  - **Docker (`Dockerfile`):** Examines `FROM` instructions (including `--platform` flags), inspects base image manifests (via Docker Hub API with caching and authentication) for multi-arch support (specifically `linux/arm64`), and identifies potentially architecture-specific commands within Dockerfile stages.
  - **Dependencies:**
    - **Python (`requirements.txt`):** Checks PyPI packages using PyPI API data (classifiers, wheel types) and external `arm64-python-wheel-tester` results (fetched from GitHub Actions artifacts) to identify potential native code compilation issues on ARM64. Handles version specifiers and caching.
    - **JavaScript (`package.json`):** Checks npm packages by resolving versions, fetching metadata from the npm registry, and inspecting fields like `cpu`, `os`, `binary`, and `scripts` (`node-gyp`) for native dependencies or ARM compatibility indicators. Handles caching.
- **Configurable Analysis:** Easily enable or disable specific analyzers via environment variables.
- **LLM Summarization (Optional):** Uses AWS Bedrock (e.g., Claude 3 Sonnet/Haiku) via Langchain to provide a natural language summary of the analysis results and recommendations.
- **Asynchronous Processing:** Uses AWS SQS to decouple Slack request handling from the potentially long-running analysis task, ensuring Slack's 3-second timeout is met.
- **Secure:** Verifies Slack request signatures to ensure requests originate from Slack.
- **Extensible:** Designed with interfaces and clear separation of concerns to make adding new analyzers straightforward.

## Architecture

The bot utilizes a serverless architecture on AWS:

```
+---------+      +-----------------+      +-------------+      +-------------------------+      +----------+
|  Slack  |<---->| API Gateway     |<---->| SQS Queue   |<---->| ARMCompatibilityBot     |<---->|  GitHub  |
| (User)  |      | (Gateway Lambda)|      |             |      | (Processing Lambda)     |      |   API    |
+---------+      +-----------------+      +-------------+      +-------------------------+      +----------+
     ^                                                             |          ^                     ^  | Docker Hub
     |                                                             |          | LLM Summary         |  | API/Registry
     |-------------------------------------------------------------+          v                     +--+
                                                                      +---------------+
                                                                      | AWS Bedrock   |
                                                                      | (LLM Service) |
                                                                      +---------------+
```

1. **Slack:** Users interact with the bot via mentions (`@ARMCompatBot analyze <repo_url>`).
2. **API Gateway (Gateway Lambda):** Receives the HTTPS request from Slack.
   - Verifies the Slack request signature using the `SLACK_SIGNING_SECRET`.
   - If valid, places the entire Slack event payload into an SQS queue.
   - Immediately returns a `200 OK` response to Slack to meet the 3-second requirement.
3. **SQS Queue:** Acts as a buffer, decoupling the gateway from the main processing logic. This handles Slack retries and allows for potentially longer analysis times.
4. **ARMCompatibilityBot (Processing Lambda):**
   - Triggered by new messages in the SQS queue.
   - Parses the Slack event from the SQS message (`sqs_processor.py`).
   - Initializes core services (`GithubService`, `LLMService`, `DockerService` indirectly via `docker_analyzer`) and the `AnalysisOrchestrator`.
   - The `SlackHandler` processes the command (`analyze` or `help`).
   - If `analyze`:
     - Sends an acknowledgment message back to the Slack thread.
     - The `AnalysisOrchestrator` uses the `GithubService` to fetch repository data.
     - Relevant files are passed to _enabled_ `Analyzers` (Terraform, Docker, Dependency).
     - Analyzers perform checks (e.g., instance types, base images/manifests, package compatibility).
     - Results are aggregated.
     - (Optional) The `LLMService` summarizes the results using AWS Bedrock.
     - The `SlackHandler` formats the results (LLM summary or structured data) using `slack/utils.py`.
     - The final result message is posted back to the original Slack thread by updating the acknowledgment message.
5. **GitHub API:** Used by `GithubService` to fetch repository information and file contents. Also used by `python_checker` to download wheel tester results.
6. **Docker Hub Registry/API:** Used by `DockerAnalyzer` to fetch image manifests.
7. **AWS Bedrock:** Used by `LLMService` to generate analysis summaries.

## Setup & Deployment

### Prerequisites

- AWS Account
- Python 3.9+ installed locally
- AWS CLI configured with appropriate permissions (SQS, Lambda, IAM, CloudWatch Logs, Bedrock `InvokeModel`)
- AWS SAM CLI (recommended for deployment) or similar serverless deployment tool
- A Slack workspace and permissions to create Slack Apps.
- A GitHub Personal Access Token (PAT) with `repo` scope (read access to repositories).
- (Optional but Recommended for Docker analysis) Docker Hub credentials (username/password or PAT).

### Steps

1. **Create Slack App:**

   - Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app.
   - **Add Features & Functionality:**
     - **Bots:** Add a Bot User.
     - **Event Subscriptions:**
       - Enable Events.
       - _Subscribe to bot events:_ Add `app_mention`.
       - You will need the API Gateway URL _after_ deployment for the Request URL field. Slack will send a challenge request here that the gateway Lambda must handle (though challenge handling via SQS is tricky, signature validation is key).
     - **Permissions (OAuth & Permissions):**
       - Add the following Bot Token Scopes:
         - `app_mentions:read` (to receive mentions)
         - `chat:write` (to post messages)
       - Install the app to your workspace.
   - **Note down:**
     - `SLACK_BOT_TOKEN` (starts with `xoxb-`) from the "OAuth & Permissions" page.
     - `SLACK_SIGNING_SECRET` from the "Basic Information" page.

2. **Create GitHub Token:**

   - Go to your GitHub settings -> Developer settings -> Personal access tokens -> Tokens (classic).
   - Generate a new token with the `repo` scope (or `public_repo` if only analyzing public repositories).
   - **Note down:** The generated `GITHUB_TOKEN`. **Treat this like a password.**

3. **Configure Environment Variables:**

   - Create a `.env` file in the `alpha/lambdas/ARMCompatibilityBot/src/` directory for local development (this file should **NOT** be committed to Git). See `.env.sample`.
   - Populate it with the necessary values (see [Configuration](#configuration) section below).
   - For deployment, these variables need to be set directly in the Lambda function configurations (both the Gateway Lambda and the Processing Lambda where applicable). Consider using AWS Secrets Manager for sensitive values like tokens and passwords in production.

4. **Deploy using AWS SAM (Recommended):**

   - You will need a `template.yaml` file (not provided in the code snippet, but standard for SAM). This template should define:
     - The SQS Queue.
     - The IAM Roles for the Lambdas (permissions for SQS, CloudWatch, GitHub access via internet, Bedrock `InvokeModel`).
     - The **Gateway Lambda Function** (`slack_bot_gateway/lambda_function.py`):
       - Triggered by API Gateway (HTTP API recommended).
       - Environment variables: `SQS_QUEUE_URL`, `SLACK_SIGNING_SECRET`, `LOG_LEVEL`.
     - The **Processing Lambda Function** (`ARMCompatibilityBot/src/lambda_function.py`):
       - Triggered by the SQS Queue.
       - Environment variables: All variables listed in [Configuration](#configuration), including `SQS_QUEUE_URL`.
       - Set an appropriate memory size (e.g., 512MB - 1024MB) and timeout (e.g., 2-5 minutes) due to potential network calls and analysis complexity.
   - Run `sam build` and `sam deploy --guided`.

5. **Update Slack Event Subscription URL:**

   - Once deployed, copy the API Gateway Invoke URL.
   - Go back to your Slack App configuration -> Event Subscriptions.
   - Paste the URL into the "Request URL" field. Slack may send a `url_verification` request. The Gateway Lambda must pass signature validation for Slack to show "Verified".
   - Save changes.

6. **Invite Bot to Channels:** Invite the `@ARMCompatBot` (or whatever you named it) to the Slack channels where you want to use it.

## Usage

Interact with the bot in a channel it has been invited to, or via direct message:

1. **Analyze a Repository:**

   ```slack
   @ARMCompatBot analyze https://github.com/owner/repo-name
   ```

   Replace `https://github.com/owner/repo-name` with the actual URL of the public or private (if your `GITHUB_TOKEN` has access) repository you want to analyze.

2. **Get Help:**

   ```slack
   @ARMCompatBot help
   ```

The bot will first post an acknowledgment message in a thread, then update that message with the analysis results or an LLM summary once complete. If errors occur, they will be reported in the thread.

## Configuration

The bot uses environment variables for configuration. These are primarily managed in `config.py` and accessed by various modules.

| Variable                     | `src/config.py` | Gateway Lambda | Description                                                                                             | Default                                   |     Required      |
| :--------------------------- | :-------------: | :------------: | :------------------------------------------------------------------------------------------------------ | :---------------------------------------- | :---------------: |
| `GITHUB_TOKEN`               |       ✅        |       ❌       | GitHub Personal Access Token with `repo` scope.                                                         | `""`                                      |        ✅         |
| `SLACK_BOT_TOKEN`            |       ✅        |       ❌       | Slack Bot Token (starts with `xoxb-`).                                                                  | `""`                                      |        ✅         |
| `SLACK_SIGNING_SECRET`       |       ✅        |       ✅       | Slack App Signing Secret. Used by Gateway to verify requests.                                           | `""`                                      |        ✅         |
| `SQS_QUEUE_URL`              |       ✅        |       ✅       | The URL of the SQS queue used to buffer requests.                                                       | `None`                                    |        ✅         |
| `ENABLE_LLM`                 |       ✅        |       ❌       | Set to `True` to enable LLM summarization, `False` otherwise.                                           | `True`                                    |        No         |
| `BEDROCK_REGION`             |       ✅        |       ❌       | AWS region where Bedrock is available (e.g., `us-east-1`). Required if `ENABLE_LLM` is `True`.          | `us-east-1`                               |      If LLM       |
| `BEDROCK_MODEL_ID`           |       ✅        |       ❌       | Bedrock Model ID (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`). Required if `ENABLE_LLM` is `True`. | `anthropic.claude-3-sonnet-20240229-v1:0` |      If LLM       |
| `LLM_LANGUAGE`               |       ✅        |       ❌       | Language for LLM prompts and responses (e.g., `english`, `korean`).                                     | `english`                                 |        No         |
| `ENABLE_TERRAFORM_ANALYZER`  |       ✅        |       ❌       | Set to `True` to enable the Terraform analyzer.                                                         | `False`                                   |        No         |
| `ENABLE_DOCKER_ANALYZER`     |       ✅        |       ❌       | Set to `True` to enable the Docker analyzer.                                                            | `False`                                   |        No         |
| `ENABLE_DEPENDENCY_ANALYZER` |       ✅        |       ❌       | Set to `True` to enable the Dependency analyzer (Python & JS).                                          | `True`                                    |        No         |
| `LOG_LEVEL`                  |       ✅        |       ✅       | Logging level for the application (e.g., `INFO`, `DEBUG`, `WARNING`).                                   | `INFO`                                    |        No         |
| `DOCKERHUB_USERNAME`         |       ✅        |       ❌       | Docker Hub username for manifest inspection via API.                                                    | `""`                                      | If Docker Enabled |
| `DOCKERHUB_PASSWORD`         |       ✅        |       ❌       | Docker Hub password or Personal Access Token (PAT) for manifest inspection.                             | `""`                                      | If Docker Enabled |

_(Note: `python-dotenv` is used to load these from a `.env` file during local development if it exists.)_

## Code Structure

```
alpha/
├── lambdas/
│   ├── ARMCompatibilityBot/        # Processing Lambda
│   │   ├── README.md               # Internal README for this lambda (bug fixes, etc.)
│   │   └── src/
│   │       ├── .env.sample         # Sample environment file
│   │       ├── analysis_orchestrator.py # Coordinates the analysis process
│   │       ├── config.py           # Loads and provides configuration
│   │       ├── lambda_function.py  # AWS Lambda handler for processing SQS messages
│   │       ├── sqs_processor.py    # Parses SQS message body to get Slack event
│   │       │
│   │       ├── analyzers/          # Code for specific analysis modules
│   │       │   ├── __init__.py
│   │       │   ├── base_analyzer.py # Abstract base class for analyzers
│   │       │   ├── docker_analyzer.py # Analyzes Dockerfiles and manifests
│   │       │   ├── terraform_analyzer.py # Analyzes Terraform instance types
│   │       │   └── dependency_analyzer/ # Analyzes software dependencies
│   │       │       ├── __init__.py
│   │       │       ├── base_checker.py # Abstract base class for dependency checkers
│   │       │       ├── js_checker.py   # Checks Node.js (package.json) dependencies
│   │       │       ├── manager.py      # Manages different dependency checkers
│   │       │       └── python_checker.py # Checks Python (requirements.txt) dependencies
│   │       │
│   │       ├── core/               # Core interfaces or shared components
│   │       │   └── interfaces.py   # Defines Analyzer and DependencyChecker interfaces
│   │       │
│   │       ├── services/           # Clients for interacting with external APIs
│   │       │   ├── __init__.py
│   │       │   ├── github_service.py # Interacts with the GitHub API
│   │       │   └── llm_service.py  # Interacts with AWS Bedrock (Langchain)
│   │       │
│   │       └── slack/              # Slack-specific interactions and formatting
│   │           ├── __init__.py
│   │           ├── handler.py      # Handles Slack event callbacks and commands
│   │           └── utils.py        # Formats messages using Slack Block Kit
│   │
│   └── slack_bot_gateway/      # Gateway Lambda
│       └── lambda_function.py  # Handles Slack verification and SQS forwarding
│
├── readme.md                   # This file (English README)
└── readme.ko.md                # Korean README
```

## Extending the Bot

### Adding a New Analyzer

1. **Create Analyzer Class:**
   - Create a new Python file in the `src/analyzers/` directory (e.g., `my_analyzer.py`).
   - Define a class (e.g., `MyAnalyzer`) that inherits from `analyzers.base_analyzer.BaseAnalyzer`.
2. **Implement Abstract Methods:**
   - `analyze(self, file_content: str, file_path: str) -> Dict[str, Any]`: Implement the logic to parse a single file's content and return raw findings.
   - `aggregate_results(self, analysis_outputs: List[Dict[str, Any]]) -> Dict[str, Any]`: Implement logic to combine results from multiple files analysed by this type. The return dictionary should ideally contain keys like `results`, `recommendations`, `reasoning`.
   - `relevant_file_patterns(self) -> List[str]`: Return a list of regex patterns that match file paths relevant to this analyzer (e.g., `[r"\.myconfig$"]`).
   - `analysis_key(self) -> str`: Return the unique key under which this analyzer's aggregated results will be stored in the final output (e.g., `"my_config_findings"`).
3. **Register Analyzer:**
   - Open `src/analysis_orchestrator.py`.
   - Import your new analyzer class.
   - Add a mapping for it in the `_analyzer_instances` dictionary within the `__init__` method (e.g., `"my_analyzer": MyAnalyzer`).
4. **Add Configuration:**
   - Open `src/config.py`.
   - Add a new environment variable entry in `ENABLED_ANALYZERS` (e.g., `"my_analyzer": os.environ.get("ENABLE_MY_ANALYZER", "False").lower() == "true"`).
5. **Update LLM Prompt (Optional):**
   - If using the LLM summary, modify the `PROMPT_TEMPLATE_STR` in `src/services/llm_service.py` to instruct the LLM on how to interpret and present findings from your new `analysis_key`.

### Adding a New Dependency Checker

1. **Create Checker Class:**
   - Create a new file in `src/analyzers/dependency_analyzer/` (e.g., `java_checker.py`).
   - Define a class (e.g., `JavaDependencyChecker`) inheriting from `analyzers.dependency_analyzer.base_checker.BaseDependencyChecker`.
2. **Implement Abstract Methods:**
   - `parse_dependencies(self, file_content: str, file_path: str) -> List[Dict[str, Any]]`: Parse the dependency manifest file (e.g., `pom.xml`) and return a list of dependency dictionaries.
   - `check_compatibility(self, dependency_info: Dict[str, Any]) -> Dict[str, Any]`: Check the ARM compatibility of a single parsed dependency (e.g., check Maven Central, use heuristics). Return a dictionary including `compatible` (bool/str) and `reason` (str).
3. **Register Checker:**
   - Open `src/analyzers/dependency_analyzer/manager.py`.
   - Import your new checker class.
   - Add an instance to the `_checkers` dictionary in `__init__` (e.g., `"java": JavaDependencyChecker()`).
   - Update `_get_checker_and_type` to recognize the relevant file path (e.g., `elif file_path.lower().endswith("pom.xml"): return self._checkers.get("java"), "java"`).
   - Update `relevant_file_patterns` in `DependencyManager` to include the pattern for the new manifest file (e.g., `r"pom\.xml$"`).
   - (Optional) Adjust recommendation/reasoning generation in `aggregate_results` for the new language type.

### Modifying Slack Messages

- Edit the functions within `src/slack/utils.py` to change the structure or content of the messages sent to Slack using Block Kit.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs, feature requests, or improvements.

## License

This project is licensed under the Apache License 2.0.

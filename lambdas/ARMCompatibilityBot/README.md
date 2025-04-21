# ARMCompatibilityBot Lambda Function

This AWS Lambda function analyzes Docker images and other resources to determine compatibility with ARM architecture (Graviton) for potential cloud cost savings.

## Bug Fixes

### 2023-04-21: Fixed Slack Message Length Issue

1. Fixed error: `slack_sdk.errors.SlackApiError: invalid_blocks` with error message `must be less than 3001 characters`
   - Updated `format_llm_summary_blocks` to split long LLM summaries into multiple blocks
   - Added logic to find clean split points at newlines when possible
   - Added dividers between split content chunks for better readability

### 2023-04-21: Fixed NullPointerException in `docker_analyzer.py`

1. Fixed error: `AttributeError: 'NoneType' object has no attribute 'get'` in `aggregate_results` function

   - Initialize `details` field with an empty dict in `_check_image_compatibility_via_manifest`
   - Added null checks in error handling blocks for `details` field
   - Added null checks for `manifest_info` in `aggregate_results`

2. Renamed key from `image_assessments` to `results` in the return value of `aggregate_results` to match orchestrator expectations

## Dependencies

The function requires:

- `semantic_version`
- `httpx`
- `semver`

## Structure

- `src/lambda_function.py` - Entry point for Lambda
- `src/analysis_orchestrator.py` - Orchestrates analysis of repositories
- `src/analyzers/` - Contains various analyzers:
  - `docker_analyzer.py` - Analyzes Dockerfiles for ARM compatibility
  - `terraform_analyzer.py` - Analyzes Terraform files
  - `base_analyzer.py` - Abstract base class for analyzers
- `src/slack/` - Slack integration components
  - `utils.py` - Contains Slack formatting functions and API helpers
  - `handler.py` - Handles Slack events and interactions
- `src/services/` - Supporting services
- `src/core/` - Core functionality components

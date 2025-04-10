import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists (useful for local development)
# In AWS Lambda, environment variables are set directly in the function configuration.
load_dotenv()

# --- Logging Configuration ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
# Basic logging setup
log_level_int = logging.getLevelName(LOG_LEVEL)  # Get the integer value for the level
# Get the root logger
logger = logging.getLogger()
# Remove existing handlers if any (important for Lambda)
if logger.hasHandlers():
    logger.handlers.clear()
logger.setLevel(log_level_int)
# Add a basic StreamHandler
ch = logging.StreamHandler()
ch.setLevel(log_level_int)  # Set level for the handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.info(f"Logging level set to: {LOG_LEVEL}")


# --- GitHub Configuration ---
# Required for accessing GitHub repositories. Generate a token with 'repo' scope.
# https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    logger.warning(
        "GITHUB_TOKEN environment variable not set. GitHub API rate limits may be encountered."
    )


# --- LLM Configuration ---
# Flag to enable/disable LLM summarization features.
ENABLE_LLM = os.environ.get("ENABLE_LLM", "True").lower() == "true"

# AWS Bedrock Configuration (if ENABLE_LLM is True)
# Specify the AWS region where Bedrock service is available.
BEDROCK_REGION = os.environ.get(
    "BEDROCK_REGION", "us-east-1"
)  # Defaulting to us-east-1, adjust if needed

# Specify the Bedrock model ID to use for summarization.
# Example: Anthropic Claude 3 Sonnet: anthropic.claude-3-sonnet-20240229-v1:0
# Example: Anthropic Claude 3 Haiku: anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
)

# Language preference for LLM prompts/summaries (Consider making this an env var if needed)
LLM_LANGUAGE = "english"  # or "korean", etc.


# --- Analyzer Configuration ---
# Control which analysis modules are active. Set environment variables to "true" or "false".
ENABLED_ANALYZERS = {
    "terraform": os.environ.get("ENABLE_TERRAFORM_ANALYZER", "False").lower() == "true",
    "docker": os.environ.get("ENABLE_DOCKER_ANALYZER", "False").lower() == "true",
    "dependency": os.environ.get("ENABLE_DEPENDENCY_ANALYZER", "True").lower()
    == "true",
}

# --- Slack Configuration ---
# These are typically set in the Lambda environment variables by the deployment process
# or loaded via dotenv for local testing.
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")

if not SLACK_BOT_TOKEN:
    logger.warning("SLACK_BOT_TOKEN environment variable not set.")
if not SLACK_SIGNING_SECRET:
    logger.warning("SLACK_SIGNING_SECRET environment variable not set.")

# --- SQS Configuration ---
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")
if not SQS_QUEUE_URL:
    logger.warning(
        "SQS_QUEUE_URL environment variable not set! SQS message deletion will fail."
    )

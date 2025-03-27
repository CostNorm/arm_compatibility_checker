import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# GitHub API token for higher rate limits (optional but recommended)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Google API key for Gemini model
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# Flags for enabling/disabling components
ENABLE_LLM = os.environ.get("ENABLE_LLM", "True").lower() == "true"

# Bedrock Configuration (Add these)
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "ap-northeast-2") # Or your preferred region
# Example: Claude 3 Sonnet. Haiku is faster/cheaper: anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")

LLM_LANGUAGE = "english" # "korean"

# 분석 모듈 활성화 설정 추가
ENABLED_ANALYZERS = {
    "terraform": False,
    "docker": False,
    "dependency": True,
}

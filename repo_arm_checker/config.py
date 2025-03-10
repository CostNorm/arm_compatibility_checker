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

# 기존 설정
ENABLE_LLM = True

# 분석 모듈 활성화 설정 추가
ENABLED_ANALYZERS = {
    "terraform": False,
    "docker": False,
    "dependency": True,
}

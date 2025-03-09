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

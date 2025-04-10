import os
import json
import logging
from typing import Dict, Any, Optional

# Langchain imports
from langchain_aws import ChatBedrock

# from langchain_google_genai import ChatGoogleGenerativeAI # Uncomment if adding Gemini support
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models.chat_models import BaseChatModel

# Configuration import (Only needed for potential future Google API Key)
# from config import GOOGLE_API_KEY # Keep for potential future use or alternative

logger = logging.getLogger(__name__)

# --- Prompt Template ---
# Defined at module level as it's constant
PROMPT_TEMPLATE_STR = """
You are an expert in cloud computing architecture and ARM64 compatibility assessment.
Based on the following analysis of a GitHub repository, provide a clear assessment of
its ARM64 compatibility, including specific recommendations for migration if applicable.

Compatibility Analysis Data (JSON format):
```json
{compatibility_result_json}
```

Instructions:
1. Start with an overall assessment of ARM64 compatibility (compatible, incompatible, unknown) based on the 'overall_compatibility' field and the reasoning provided in the context.
2. IMPORTANT: Only discuss and provide recommendations for analyzers that were actually enabled during the analysis.
3. The enabled analyzers are listed in the `context.enabled_analyzers` field within the JSON data. ONLY discuss these enabled analyzers.
4. For each *enabled* analyzer:
   - If "terraform" is enabled and findings exist: Discuss EC2 instance type compatibility findings (`instance_types` list). Mention specific incompatible types and suggestions if available.
   - If "docker" is enabled and findings exist: Discuss Docker base image compatibility (`docker_images` list). Mention specific problematic images and suggestions (like platform specification).
   - If "dependency" is enabled and findings exist: Discuss the compatibility of software dependencies (`dependencies` list). Highlight incompatible or partially compatible direct/transitive dependencies (Python/Node.js).
5. Summarize the key `recommendations` provided in the JSON data, grouping them logically if possible (e.g., by file or type).
6. Do NOT mention or provide recommendations for disabled analyzers. If no relevant findings exist for an enabled analyzer, briefly state that.
7. Keep your response concise, technical, and directly useful to engineers. Use bullet points for clarity.
8. Format for Slack: Your response will be displayed directly in a Slack message using Block Kit's mrkdwn.
    - Do NOT use Markdown headings like # or ##.
    - Instead, use *bold text* for titles and section headings.
    - You can continue to use standard lists (* item, 1. item), multi-line code blocks (```python ... ```), inline code (`code`), bold (*text*), italics (_text_), and strikethrough (~text~).
9. Respond entirely in **{language}**.

Assessment and Recommendations:
"""


class LLMService:
    """Handles interaction with the configured Language Model for summarization."""

    def __init__(
        self,
        enabled: bool,
        bedrock_region: Optional[str],
        bedrock_model_id: Optional[str],
        language: str,
        # google_api_key: Optional[str] = None # Add if implementing Google LLM
    ):
        """
        Initializes the LLM client based on provided configuration.

        Args:
            enabled: Whether the LLM service should be active.
            bedrock_region: AWS region for Bedrock.
            bedrock_model_id: Model ID for Bedrock.
            language: The language for the LLM response.
            # google_api_key: API key for Google Generative AI (optional).
        """
        self.llm_client: Optional[BaseChatModel] = None
        self.is_enabled = enabled
        self.bedrock_region = bedrock_region
        self.bedrock_model_id = bedrock_model_id
        self.language = language
        # self.google_api_key = google_api_key

        if self.is_enabled:
            if self.bedrock_region and self.bedrock_model_id:
                try:
                    # Initialize Langchain ChatBedrock
                    # Note: The region parameter in ChatBedrock might need adjustment based on library version or specific AWS setup.
                    # If 'region' is not a direct parameter, it might be picked up from boto3 session or environment variables.
                    # Explicitly setting region_name is often clearer.
                    self.llm_client = ChatBedrock(
                        model_id=self.bedrock_model_id,
                        model_kwargs={"temperature": 0.1, "max_tokens": 8000},
                        region_name=self.bedrock_region,  # Use region_name for clarity
                    )
                    logger.info(
                        f"ChatBedrock initialized with model: {self.bedrock_model_id} in region {self.bedrock_region}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to initialize ChatBedrock: {e}", exc_info=True
                    )
                    self.is_enabled = False  # Disable if initialization fails
            # TODO: Add initialization for Google Gemini if needed
            # elif self.google_api_key:
            #    try:
            #       self.llm_client = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=self.google_api_key, ...)
            #       logger.info("ChatGoogleGenerativeAI initialized.")
            #    except Exception as e:
            #        logger.error(f"Failed to initialize Google LLM: {e}", exc_info=True)
            #        self.is_enabled = False
            else:
                logger.warning(
                    "LLM is enabled but required configurations (Bedrock or Google) are missing."
                )
                self.is_enabled = False

        if not self.is_enabled:
            logger.warning(
                "LLM Service is disabled due to configuration or initialization issues."
            )

        # Setup prompt and parser (can be done even if LLM is disabled)
        self.prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE_STR)
        self.output_parser = StrOutputParser()

    def summarize_analysis(self, compatibility_result: Dict[str, Any]) -> str:
        """
        Uses the configured LLM via Langchain to summarize the ARM compatibility results.

        Args:
            compatibility_result: The dictionary containing the aggregated analysis results.

        Returns:
            A string containing the LLM-generated summary, formatted for Slack mrkdwn.

        Raises:
            RuntimeError: If LLM is not enabled or not initialized successfully.
            Exception: If the LLM invocation fails.
        """
        if not self.is_enabled or not self.llm_client:
            raise RuntimeError("LLM Service is not enabled or failed to initialize.")

        logger.info("Generating LLM summary for compatibility results...")
        try:
            # Convert the result dictionary to a JSON string for the prompt
            # Using indent=2 makes it more readable for the LLM (and debugging)
            # Pass the dictionary directly if the LLM/Langchain handles it better
            # compatibility_result_json = json.dumps(compatibility_result, indent=2, ensure_ascii=False)

            # Create the Langchain chain
            chain = self.prompt | self.llm_client | self.output_parser

            # Invoke the chain
            # Pass the dictionary directly to the chain's input variables
            summary = chain.invoke(
                {
                    "compatibility_result_json": json.dumps(compatibility_result),
                    "language": self.language,  # Use instance language
                }
            )
            logger.info("LLM summary generated successfully.")
            return summary

        except Exception as e:
            logger.error(f"Error during LLM summarization: {e}", exc_info=True)
            raise  # Re-raise the exception to be handled by the caller


# Example of how it might be used (optional, for clarity)
# if __name__ == "__main__":
#     # This part would not run in Lambda, just for local testing/understanding
#     logging.basicConfig(level=logging.INFO)
#     # Load .env if running locally
#     from dotenv import load_dotenv
#     load_dotenv()
#
#     # Get config from environment for local testing
#     test_bedrock_region = os.environ.get("BEDROCK_REGION", "us-west-2")
#     test_bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
#     test_enable_llm = os.environ.get("ENABLE_LLM", "True").lower() == "true"
#     test_llm_language = "english"
#
#     llm_service = LLMService(
#         enabled=test_enable_llm,
#         bedrock_region=test_bedrock_region,
#         bedrock_model_id=test_bedrock_model_id,
#         language=test_llm_language
#     )
#
#     if llm_service.is_enabled:
#         # Example dummy data
#         dummy_result = {
#             "overall_compatibility": "incompatible",
#             "instance_types": [{"compatible": False, "current": "t2.micro", "reason": "No ARM equivalent available", "file": "main.tf"}],
#             "docker_images": [],
#             "dependencies": [{"dependency": "old-package==1.0", "compatible": False, "reason": "Known issue", "file": "reqs.txt", "direct": True}],
#             "recommendations": ["Replace t2.micro", "Replace old-package"],
#             "context": {
#                 "analysis_summary": {"terraform_files_analyzed": 1, "dockerfile_files_analyzed": 0, "dependency_files_analyzed": 1},
#                 "reasoning": ["Instance type t2.micro has no ARM equivalent.", "Dependency old-package is incompatible."],
#                 "process_description": "Analyzed Terraform and dependencies.",
#                 "enabled_analyzers": ["terraform", "dependency"],
#                 "statistics": {"incompatible_items": 2, "compatible_items": 0, "unknown_items": 0, "total_recommendations": 2}
#             }
#         }
#         try:
#             summary = llm_service.summarize_analysis(dummy_result)
#             print("\n--- LLM Summary ---")
#             print(summary)
#         except Exception as e:
#             print(f"\n--- Error during summarization: {e} ---")
#     else:
#         print("LLM Service is disabled.")

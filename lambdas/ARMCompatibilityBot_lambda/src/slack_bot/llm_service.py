import os
import json
import logging
from typing import Dict, Any


from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


from config import (
    ENABLE_LLM,
    BEDROCK_REGION,
    BEDROCK_MODEL_ID,
    GOOGLE_API_KEY, # Keep for potential future use or alternative
    LLM_LANGUAGE,
)

logger = logging.getLogger()

# --- LLM Client Initialization ---
llm = None
if ENABLE_LLM:
    if BEDROCK_REGION and BEDROCK_MODEL_ID:
        try:
            # Initialize Langchain ChatBedrock
            llm = ChatBedrock(
                model_id=BEDROCK_MODEL_ID,
                model_kwargs={"temperature": 0.1, "max_tokens": 8000},
                region="us-west-2"
            )
            logger.info(f"ChatBedrock initialized with model: {BEDROCK_MODEL_ID} in region {BEDROCK_REGION}")
        except Exception as e:
            logger.error(f"Failed to initialize ChatBedrock: {e}", exc_info=True)
            ENABLE_LLM = False # Disable LLM if initialization fails
    # TODO: Add initialization for Google Gemini if needed as an alternative
    # elif GOOGLE_API_KEY:
    #    from langchain_google_genai import ChatGoogleGenerativeAI
    #    try:
    #       llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=GOOGLE_API_KEY, ...)
    #       logger.info("ChatGoogleGenerativeAI initialized.")
    #    except Exception as e:
    #        logger.error(f"Failed to initialize Google LLM: {e}", exc_info=True)
    #        ENABLE_LLM = False
    else:
        logger.warning("LLM is enabled but required configurations (Bedrock or Google) are missing.")
        ENABLE_LLM = False

# --- Prompt Template ---
# Using the user-provided template
prompt_template_str = """
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
    - You can continue to use standard lists (* item, 1. item), multi-line code blocks (python ...), inline code (code), bold (*text*), italics (_text_), and strikethrough (~text~).
9. Respond entirely in **{language}**.

Assessment and Recommendations:
"""

prompt = ChatPromptTemplate.from_template(prompt_template_str)
output_parser = StrOutputParser()

# --- Summarization Function ---
def summarize_analysis_with_llm(compatibility_result: Dict[str, Any]) -> str:
    """
    Uses the configured LLM via Langchain to summarize the ARM compatibility results.

    Args:
        compatibility_result: The dictionary returned by check_arm_compatibility.

    Returns:
        A string containing the LLM-generated summary in Markdown format.

    Raises:
        RuntimeError: If LLM is not enabled or not initialized.
        Exception: If the LLM invocation fails.
    """
    if not ENABLE_LLM or not llm:
        raise RuntimeError("LLM is not enabled or failed to initialize.")

    logger.info("Generating LLM summary for compatibility results...")
    try:
        # Convert the result dictionary to a JSON string for the prompt
        # Using indent=2 makes it more readable for the LLM (and debugging)
        compatibility_result_json = json.dumps(compatibility_result, indent=2, ensure_ascii=False)

        # Create the Langchain chain
        chain = prompt | llm | output_parser
        # print(llm.invoke("안녕하세요"))

        # Invoke the chain
        print(f"compatibility_result: ", compatibility_result)
        summary = chain.invoke({"compatibility_result_json": compatibility_result, "language": LLM_LANGUAGE})
        logger.info("LLM summary generated successfully.")
        print(summary)
        return summary

    except Exception as e:
        logger.error(f"Error during LLM summarization: {e}", exc_info=True)
        raise # Re-raise the exception to be handled by the caller


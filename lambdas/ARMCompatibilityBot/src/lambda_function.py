import os
import json
import logging
import boto3
from slack_sdk import WebClient
from typing import Optional

# Refactored imports
from config import (
    logger,  # Import the configured logger
    SLACK_BOT_OAUTH_TOKEN,
    SQS_QUEUE_URL,
    GITHUB_TOKEN,  # Import GITHUB_TOKEN for service initialization
    BEDROCK_REGION,  # Import BEDROCK_REGION for service initialization
    BEDROCK_MODEL_ID,  # Import BEDROCK_MODEL_ID for service initialization
    ENABLE_LLM,  # Import ENABLE_LLM for service initialization
    LLM_LANGUAGE,  # Import LLM_LANGUAGE for service initialization
)
from sqs_processor import parse_sqs_message
from slack.handler import SlackHandler  # Import the new handler class
from services.github_service import (
    GithubService,
)  # Needed by SlackHandler indirectly via Orchestrator
from services.llm_service import LLMService  # Needed by SlackHandler
from analysis_orchestrator import AnalysisOrchestrator  # Needed by SlackHandler


# --- Client Initialization ---
# Initialize SQS client (consider lazy initialization if needed)
sqs = boto3.client("sqs")

# Initialize Slack client
slack_client: Optional[WebClient] = None
if SLACK_BOT_OAUTH_TOKEN:
    try:
        slack_client = WebClient(token=SLACK_BOT_OAUTH_TOKEN)
        # Test authentication to ensure the token is valid early
        auth_test = slack_client.auth_test()
        logger.info(
            f"Slack client initialized successfully for bot user: {auth_test.get('user_id')}"
        )
    except Exception as slack_init_err:
        logger.error(
            f"Failed to initialize or authenticate Slack client: {slack_init_err}",
            exc_info=True,
        )
        slack_client = None  # Ensure client is None if init fails
else:
    # Error already logged in config.py
    pass

if not SQS_QUEUE_URL:
    # Error already logged in config.py
    pass


# --- Instantiate Core Services and Handler ---
# These can be instantiated once per Lambda container execution
# Pass dependencies explicitly
# Initialize services using config values
github_service = GithubService(github_token=GITHUB_TOKEN)
llm_service = LLMService(
    enabled=ENABLE_LLM,
    bedrock_region=BEDROCK_REGION,
    bedrock_model_id=BEDROCK_MODEL_ID,
    language=LLM_LANGUAGE,
)
analysis_orchestrator = AnalysisOrchestrator(github_service=github_service)
slack_handler = SlackHandler(
    orchestrator=analysis_orchestrator, llm_service=llm_service
)


# --- Main Lambda Handler ---
def lambda_handler(event, context):
    """
    AWS Lambda handler function triggered by SQS events.
    Processes Slack interaction payloads received via SQS using the refactored structure.
    """
    # Check for essential clients initialized during cold start
    if not slack_client:
        logger.critical("Slack client is not available. Cannot process messages.")
        # Fail fast for all records in this invocation if Slack is down
        # Returning an error or raising an exception might trigger Lambda retries depending on config
        # For now, log critical and let individual message processing fail below
        pass

    processed_count = 0
    failed_count = 0
    total_records = len(event.get("Records", []))
    logger.info(f"Received {total_records} SQS records.")

    for record in event.get("Records", []):
        receipt_handle = None
        message_processed_successfully = (
            False  # Assume failure unless explicitly marked success
        )

        try:
            # 1. Parse SQS message
            # parse_sqs_message handles retry detection and basic parsing errors
            slack_body, headers, receipt_handle = parse_sqs_message(record)

            if not receipt_handle:
                logger.error(
                    "Failed to get receipt handle for a message. It cannot be deleted."
                )
                failed_count += 1
                continue  # Move to the next record

            # If slack_body is None, parse_sqs_message determined it should be skipped (e.g., retry, parse error)
            if slack_body is None:
                logger.info(
                    f"Skipping SQS message {receipt_handle} as indicated by parser (retry or parse error)."
                )
                # Treat as 'processed' to allow deletion from SQS and prevent loops
                message_processed_successfully = True
            elif not slack_client:
                logger.error(
                    f"Skipping message {receipt_handle} processing because Slack client is not initialized."
                )
                # Do not mark as processed, let it retry or go to DLQ if configured
                failed_count += 1
            else:
                # 2. Delegate to Slack Handler
                logger.info(
                    f"Dispatching Slack interaction type '{slack_body.get('type')}' for message {receipt_handle}..."
                )
                # The handler now encapsulates the logic, including calling the orchestrator etc.
                # It should return True if the message should be deleted from SQS, False otherwise.
                message_processed_successfully = slack_handler.handle_interaction(
                    slack_body, slack_client
                )

                if message_processed_successfully:
                    logger.info(
                        f"Successfully processed interaction for message {receipt_handle}."
                    )
                    processed_count += 1
                else:
                    # Handler indicated failure, message should likely not be deleted
                    logger.error(
                        f"Slack handler failed to process interaction for message {receipt_handle}."
                    )
                    failed_count += 1

        except Exception as e:
            # Catch unexpected errors during the processing of a single record
            logger.exception(
                f"Critical error processing SQS record (ReceiptHandle: {receipt_handle}): {e}"
            )
            failed_count += 1
            # message_processed_successfully remains False, message won't be deleted

        finally:
            # 3. Delete message from SQS if processed successfully
            if message_processed_successfully and receipt_handle and SQS_QUEUE_URL:
                try:
                    sqs.delete_message(
                        QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle
                    )
                    logger.info(
                        f"Successfully deleted message {receipt_handle} from SQS."
                    )
                except Exception as del_err:
                    # Log delete error, but the message was likely processed. Might lead to reprocessing.
                    logger.error(
                        f"Failed to delete message {receipt_handle} from SQS: {del_err}",
                        exc_info=True,
                    )
            elif not receipt_handle:
                # Should not happen if logic above is correct, but log defensively
                logger.warning(
                    "No receipt handle found for a processed record, cannot delete."
                )
            elif not message_processed_successfully:
                logger.warning(
                    f"Message {receipt_handle} was not processed successfully or handler indicated failure, will not delete."
                )
            elif not SQS_QUEUE_URL:
                # Error already logged in config.py
                pass

    # Return summary response
    summary_message = f"Processed {processed_count}/{total_records} records. Failed {failed_count}/{total_records} records."
    logger.info(summary_message)

    # Lambda execution itself succeeded, return 200. SQS handles message visibility based on deletion.
    return {
        "statusCode": 200,
        "body": json.dumps({"message": summary_message}),
    }

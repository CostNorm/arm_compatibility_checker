# src/lambda_function.py
import os
import json
import logging
import boto3
from slack_sdk import WebClient

# Use absolute imports relative to 'src' or use try/except for Lambda compatibility
try:
    from sqs_processor import parse_sqs_message
    from slack_handler import handle_slack_interaction
except ImportError:
    from .sqs_processor import parse_sqs_message
    from .slack_handler import handle_slack_interaction

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration ---
SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

# --- Initialize Clients ---
sqs = boto3.client("sqs")
slack_client = None
if SLACK_BOT_OAUTH_TOKEN:
    slack_client = WebClient(token=SLACK_BOT_OAUTH_TOKEN)
    logger.info("Slack client initialized successfully.")
else:
    logger.error(
        "SLACK_BOT_OAUTH_TOKEN environment variable not set! Slack functionality will fail."
    )

if not SQS_QUEUE_URL:
    logger.error("SQS_QUEUE_URL environment variable not set!")

# --- Main Lambda Handler ---


def lambda_handler(event, context):
    """
    AWS Lambda handler function triggered by SQS events.
    Processes Slack interaction payloads received via SQS.
    """
    # Basic checks for essential configuration
    if not slack_client:
        logger.critical("Slack client is not available. Cannot process messages.")
        # Potentially return error immediately, or let processing fail per message
        # For SQS, it's better to let it fail per message if possible
        pass  # Allow loop to run, failures will be logged per message

    if not SQS_QUEUE_URL:
        logger.critical("SQS_QUEUE_URL is not configured. Cannot delete messages.")
        # SQS processing might proceed, but deletion will fail

    processed_count = 0
    failed_count = 0

    logger.info(f"Received {len(event.get('Records', []))} SQS records.")

    for record in event.get("Records", []):
        receipt_handle = None
        message_processed_successfully = False

        try:
            # 1. Parse SQS message to get Slack payload
            slack_body, headers, receipt_handle = parse_sqs_message(record)

            if not receipt_handle:
                logger.error(
                    "Failed to get receipt handle for a message. It cannot be deleted."
                )
                # Continue to next message? Or is this record malformed?
                failed_count += 1
                continue

            # If parse_sqs_message returned None body, it might be a retry or parse error
            if slack_body is None:
                # If it was a retry (headers present), mark as processed to delete
                if headers and headers.get("x-slack-retry-num"):
                    logger.info(
                        f"Ignoring Slack retry message {receipt_handle}. Marking as processed."
                    )
                    message_processed_successfully = True
                else:
                    # Actual parsing error occurred, log already happened in parse_sqs_message
                    logger.error(
                        f"Failed to parse Slack body from SQS message {receipt_handle}. Cannot process."
                    )
                    # Decide if this should count as failure or just unprocessable message
                    message_processed_successfully = True  # Treat parse errors as 'processed' to avoid infinite loops
                # Skip further handling for this record
            else:
                # 2. Handle the extracted Slack interaction
                if not slack_client:
                    logger.error(
                        f"Skipping message {receipt_handle} processing because Slack client is not initialized."
                    )
                    # Do not mark as processed, let it retry or go to DLQ
                    failed_count += 1
                else:
                    logger.info(
                        f"Dispatching Slack interaction type '{slack_body.get('type')}' for message {receipt_handle}..."
                    )
                    # handle_slack_interaction returns True if processing (even if functionally failed) completed
                    # and the SQS message should be deleted. False means a critical error occurred during handling.
                    message_processed_successfully = handle_slack_interaction(
                        slack_body, slack_client
                    )
                    if message_processed_successfully:
                        logger.info(
                            f"Successfully dispatched handler for message {receipt_handle}."
                        )
                        processed_count += 1
                    else:
                        logger.error(
                            f"Handler failed to process Slack interaction for message {receipt_handle}."
                        )
                        failed_count += 1

        except Exception as e:
            # Catch unexpected errors during the loop iteration for a single record
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
                    logger.error(
                        f"Failed to delete message {receipt_handle} from SQS: {del_err}"
                    )
                    # Log error, but processing might have succeeded. This message might be reprocessed.
            elif not receipt_handle:
                logger.warning(
                    "No receipt handle found for a processed record, cannot delete."
                )
            elif not message_processed_successfully:
                logger.warning(
                    f"Message {receipt_handle} was not processed successfully, will not delete."
                )
            elif not SQS_QUEUE_URL:
                logger.error(
                    f"SQS_QUEUE_URL not set, cannot delete message {receipt_handle}."
                )

    # Return summary response
    summary_message = (
        f"Processed {processed_count} records. Failed {failed_count} records."
    )
    logger.info(summary_message)
    return {
        "statusCode": 200,  # Lambda executed successfully, even if some messages failed
        "body": json.dumps({"message": summary_message}),
    }

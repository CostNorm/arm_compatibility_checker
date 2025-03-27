# src/sqs_processor.py
import json
import urllib.parse
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger()


def parse_sqs_message(
    record: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    Parses an SQS record body to extract the original Slack request payload.

    Args:
        record: An SQS record dictionary.

    Returns:
        A tuple containing:
        - The parsed Slack body dictionary (or None if parsing fails).
        - The original request headers dictionary (or None).
        - The SQS message receipt handle (or None).
    """
    receipt_handle = record.get("receiptHandle")
    try:
        sqs_body_str = record.get("body")
        if not sqs_body_str:
            logger.warning("SQS record has no body.")
            return None, None, receipt_handle

        original_request_payload = json.loads(sqs_body_str)
        headers = original_request_payload.get("headers", {})

        # Check for Slack retries
        if headers.get("x-slack-retry-num"):
            logger.info(
                f"Slack retry detected (Attempt {headers.get('x-slack-retry-num')}). Skipping."
            )
            return None, headers, receipt_handle  # Return None for body to signal skip

        body_str = original_request_payload.get("body", "")
        if not body_str:
            logger.warning(
                "Original request payload in SQS message has no 'body' field."
            )
            return None, headers, receipt_handle

        # Parse Slack's body content
        slack_body = None
        if "payload=" in body_str and body_str.startswith("payload="):
            # Interaction payload (e.g., modal submit, button click)
            parsed_qs = urllib.parse.parse_qs(body_str)
            payload_str = parsed_qs.get("payload", [None])[0]
            if payload_str:
                slack_body = json.loads(payload_str)
        else:
            # Event payload (e.g., app_mention) or potentially other formats
            try:
                slack_body = json.loads(body_str)
            except json.JSONDecodeError:
                logger.error(
                    f"Failed to decode JSON body from original request: {body_str[:200]}..."
                )
                # Attempt to handle url_verification specifically if needed, though problematic via SQS
                if "challenge" in body_str and "token" in body_str:
                    logger.warning(
                        "Received potential url_verification event via SQS. This likely won't work correctly."
                    )
                    # You might return a specific marker or the raw string if you need to handle it
                    # For now, treat as unprocessable JSON
                    slack_body = {"type": "url_verification_attempt"}  # Mark it

        if slack_body is None:
            logger.warning("Could not parse Slack body from original request.")
            return None, headers, receipt_handle

        logger.info(f"Successfully parsed Slack event type: {slack_body.get('type')}")
        return slack_body, headers, receipt_handle

    except json.JSONDecodeError as json_err:
        logger.error(
            f"JSON Decode Error processing SQS message body: {json_err}. Message body: {sqs_body_str[:500]}"
        )
        return None, None, receipt_handle
    except Exception as e:
        logger.exception(f"Unexpected error parsing SQS message: {e}")
        return None, None, receipt_handle

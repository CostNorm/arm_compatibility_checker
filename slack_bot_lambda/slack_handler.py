# --- START OF MODIFIED FILE src/slack_bot/slack_handler.py ---

# slack_bot/slack_handler.py
import logging
import re
from slack_sdk import WebClient
from typing import Dict, Any, Optional

# Use absolute imports relative to the 'src' directory if running locally or packaged
try:
    from slack_utils import (
        send_slack_block_message,
        # open_slack_modal, # Removed
        format_analysis_results_blocks,
        format_error_blocks,
        format_ack_blocks,
        format_help_blocks,
        format_unknown_command_blocks,
        # format_ask_for_repo_blocks, # Removed
        format_missing_url_blocks,  # Added
    )
    from slack_bot.arm_compatibility import (
        check_compatibility,
    )  # Core analysis function
except (
    ImportError
):  # Fallback for potentially different execution environments (e.g., Lambda)
    from .slack_utils import (
        send_slack_block_message,
        # open_slack_modal, # Removed
        format_analysis_results_blocks,
        format_error_blocks,
        format_ack_blocks,
        format_help_blocks,
        format_unknown_command_blocks,
        # format_ask_for_repo_blocks, # Removed
        format_missing_url_blocks,  # Added
    )
    from arm_compatibility import check_compatibility


logger = logging.getLogger()

# --- Modal Definitions ---

# Removed get_github_repo_modal_view function

# --- Analysis Trigger Function ---


def trigger_arm_analysis(
    client: WebClient,
    channel_id: str,  # Can be user ID for DM or channel ID
    github_url: str,
    thread_ts: Optional[str] = None,  # For replying in thread (ack and results)
):
    """Sends ack, performs analysis, and sends results/error back."""
    ack_blocks = format_ack_blocks(github_url)
    ack_fallback_text = f"Starting analysis for {github_url}..."
    ack_message_ts = send_slack_block_message(
        client, channel_id, ack_blocks, ack_fallback_text, thread_ts=thread_ts
    )

    # Determine the thread for the final result. If ack was sent, reply to it. Otherwise, use the original thread_ts.
    result_thread_ts = ack_message_ts or thread_ts

    try:
        logger.info(f"Starting check_compatibility for: {github_url}")
        analysis_output = check_compatibility(
            github_url
        )  # This now returns dict with 'compatibility_result' or 'error'
        logger.info(f"Finished check_compatibility for: {github_url}")

        if "error" in analysis_output:
            logger.error(
                f"Analysis failed for {github_url}: {analysis_output['error']}"
            )
            result_blocks = format_error_blocks(github_url, analysis_output["error"])
            fallback_text = f"Error analyzing {github_url}"
        else:
            logger.info(f"Analysis successful for {github_url}")
            result_blocks = format_analysis_results_blocks(
                github_url, analysis_output["compatibility_result"]
            )
            fallback_text = f"Analysis results for {github_url}"

        send_slack_block_message(
            client, channel_id, result_blocks, fallback_text, thread_ts=result_thread_ts
        )

    except Exception as analysis_error:
        # Catch errors during the check_compatibility call itself
        logger.exception(
            f"Unexpected error during analysis process for {github_url}: {analysis_error}"
        )
        error_blocks = format_error_blocks(github_url, analysis_error)
        fallback_text = f"Critical error during analysis for {github_url}"
        send_slack_block_message(
            client, channel_id, error_blocks, fallback_text, thread_ts=result_thread_ts
        )


# --- Event Handlers ---


def handle_view_submission(body: Dict[str, Any], client: WebClient) -> bool:
    """Handles submissions from modal views."""
    view_payload = body.get("view", {})
    callback_id = view_payload.get("callback_id")
    user_id = body.get("user", {}).get("id")

    # Removed handling for 'github_repo_modal_submitted'

    # --- Add handlers for *other* potential future modals here ---
    # Example:
    # if callback_id == "some_other_modal":
    #    # Do something
    #    logger.info(f"Handling view submission for {callback_id} by user {user_id}")
    #    # ... processing logic ...
    #    return True

    logger.warning(f"Unhandled view submission callback_id: {callback_id}")
    # Return True to acknowledge the event and prevent SQS retries, even if unhandled.
    return True


def handle_block_actions(body: Dict[str, Any], client: WebClient) -> bool:
    """Handles actions within message blocks (e.g., button clicks)."""
    actions = body.get("actions", [])
    user_id = body.get("user", {}).get("id")  # User who clicked

    action_handled = False  # Track if a specific action was processed
    for action in actions:
        action_id = action.get("action_id")
        logger.info(f"Processing action_id: {action_id} from user {user_id}")

        # Removed handling for 'open_github_repo_modal'

        # --- Add handlers for *other* potential future actions here ---
        # Example:
        # if action_id == "some_other_action":
        #     # Do something
        #     action_handled = True
        #     break

    if not action_handled:
        logger.warning(f"No specific handler found for block actions: {actions}")

    # Return True to acknowledge the block_actions event itself, preventing SQS retries
    # even if no specific action was matched/handled.
    return True


def handle_app_mention(event_data: Dict[str, Any], client: WebClient) -> bool:
    """Handles 'app_mention' events."""
    if event_data.get("bot_id"):
        logger.info("Ignoring mention event from a bot.")
        return True  # Processed (ignored)

    text = event_data.get("text", "").lower()
    channel_id = event_data.get("channel")
    user_id = event_data.get("user")
    # ts of the mention message itself is crucial for threading replies correctly
    mention_message_ts = event_data.get("ts")
    # Check if the mention was *already* in a thread
    original_thread_ts = event_data.get("thread_ts")

    # --- Define target thread ---
    # Reply to the mention message itself, unless it was already in a thread.
    target_thread_ts = original_thread_ts or mention_message_ts

    if not channel_id or not user_id or not mention_message_ts:
        logger.error(f"Missing crucial data in app_mention event: {event_data}")
        return False

    github_url_pattern = r"https?://github\.com/[^/\s]+/[^/\s>\|]+"  # Improved pattern
    github_url_match = re.search(github_url_pattern, text)

    # Basic command parsing
    if "analyze" in text or "분석" in text or "check" in text or "확인" in text:
        if github_url_match:
            github_url = github_url_match.group(0).rstrip(">")  # Extract URL
            logger.info(
                f"AppMention: User {user_id} requested analysis for {github_url} in channel {channel_id}"
            )
            # Trigger analysis, replying in the thread of the mention
            trigger_arm_analysis(
                client, channel_id, github_url, thread_ts=target_thread_ts
            )
        else:
            # Ask for URL via message, not modal
            logger.info(
                f"AppMention: User {user_id} requested analysis without URL in channel {channel_id}"
            )
            # ---- MODIFIED PART ----
            # TODO: Get bot name dynamically if possible, otherwise use a default
            bot_name = "bot"  # Placeholder
            missing_url_blocks = format_missing_url_blocks(user_id, bot_name)
            send_slack_block_message(
                client,
                channel_id,
                missing_url_blocks,
                "Please provide a GitHub repository URL.",
                thread_ts=target_thread_ts,
            )
            # ---- END MODIFIED PART ----
        return True

    elif "help" in text or "도움말" in text:
        logger.info(
            f"AppMention: User {user_id} requested help in channel {channel_id}"
        )
        # TODO: Get bot name dynamically if possible
        bot_name = "bot"  # Placeholder
        help_blocks = format_help_blocks(bot_name)
        send_slack_block_message(
            client,
            channel_id,
            help_blocks,
            "Help Information",
            thread_ts=target_thread_ts,
        )
        return True

    else:
        # Unknown command
        logger.info(
            f"AppMention: User {user_id} sent unknown command in channel {channel_id}"
        )
        # TODO: Get bot name dynamically if possible
        bot_name = "bot"  # Placeholder
        unknown_blocks = format_unknown_command_blocks(user_id, bot_name)
        send_slack_block_message(
            client,
            channel_id,
            unknown_blocks,
            "Unknown command",
            thread_ts=target_thread_ts,
        )
        return True


def handle_event_callback(body: Dict[str, Any], client: WebClient) -> bool:
    """Handles 'event_callback' events by dispatching to specific event handlers."""
    event_data = body.get("event", {})
    event_type = event_data.get("type")

    if event_type == "app_mention":
        return handle_app_mention(event_data, client)
    # Add elif for other event types like 'message' if needed in the future
    # elif event_type == "message":
    #     # Handle direct messages or other message events
    #     pass

    logger.warning(f"Unhandled event_callback event type: {event_type}")
    # Return True to ack event and prevent SQS retries, even if unhandled type
    return True


# --- Main Dispatcher ---


def handle_slack_interaction(slack_body: Dict[str, Any], client: WebClient) -> bool:
    """
    Main dispatcher for incoming Slack interaction payloads (parsed from SQS).

    Args:
        slack_body: The parsed Slack payload dictionary.
        client: The initialized Slack WebClient.

    Returns:
        True if the interaction was successfully processed (or acknowledged), False otherwise.
        This indicates if the SQS message should be deleted.
    """
    interaction_type = slack_body.get("type")
    logger.info(f"Handling Slack interaction of type: {interaction_type}")

    processed_successfully = False
    if interaction_type == "view_submission":
        processed_successfully = handle_view_submission(slack_body, client)

    elif interaction_type == "block_actions":
        processed_successfully = handle_block_actions(slack_body, client)

    elif interaction_type == "event_callback":
        # Event API events (like app_mention)
        processed_successfully = handle_event_callback(slack_body, client)

    elif interaction_type == "url_verification_attempt":
        # Specific marker from parse_sqs_message
        logger.warning(
            "Acknowledging url_verification attempt received via SQS, but cannot respond correctly."
        )
        processed_successfully = True  # Treat as processed to delete SQS message

    else:
        logger.warning(
            f"Unhandled Slack interaction type: {interaction_type}. Payload: {str(slack_body)[:500]}"
        )
        processed_successfully = (
            True  # Mark as processed to prevent SQS retries for unknown types
        )

    return processed_successfully


# --- END OF MODIFIED FILE src/slack_bot/slack_handler.py ---

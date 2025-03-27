import logging
import re
import json # Import json for potential debugging if needed
from slack_sdk import WebClient
from typing import Dict, Any, Optional

logger = logging.getLogger()


from .slack_utils import (
        send_slack_block_message,
        format_analysis_results_blocks, # Keep as fallback
        format_error_blocks,
        format_ack_blocks,
        format_help_blocks,
        format_unknown_command_blocks,
        format_missing_url_blocks, # Added missing import
    )
from .arm_compatibility import (
    check_compatibility,
)
from config import ENABLE_LLM # Import ENABLE_LLM flag
from .llm_service import summarize_analysis_with_llm # Import the LLM summarizer



# --- Analysis Trigger Function ---

def trigger_arm_analysis(
    client: WebClient,
    channel_id: str,
    github_url: str,
    thread_ts: Optional[str] = None,
):
    """Sends ack, performs analysis, generates summary (LLM or basic), and sends results/error back."""
    ack_blocks = format_ack_blocks(github_url)
    ack_fallback_text = f"Starting analysis for {github_url}..."
    ack_message_ts = send_slack_block_message(
        client, channel_id, ack_blocks, ack_fallback_text, thread_ts=thread_ts
    )

    result_thread_ts = ack_message_ts or thread_ts

    try:
        logger.info(f"Starting check_compatibility for: {github_url}")
        # analysis_output contains 'repository', 'github_url', and 'compatibility_result' or 'error'
        analysis_output = check_compatibility(github_url)
        logger.info(f"Finished check_compatibility for: {github_url}")

        result_blocks = None
        fallback_text = ""

        if "error" in analysis_output:
            # --- Handle Analysis Error ---
            logger.error(f"Analysis failed for {github_url}: {analysis_output['error']}")
            result_blocks = format_error_blocks(github_url, analysis_output["error"])
            fallback_text = f"❌ ARM 호환성 분석 중 오류 발생: {github_url}"

        elif ENABLE_LLM:
            # --- Try LLM Summary ---
            try:
                logger.info("Attempting LLM summarization...")
                llm_summary = summarize_analysis_with_llm(analysis_output['compatibility_result'])
                # Format the LLM summary into simple Slack blocks
                result_blocks = [
                    {
                        "type": "section",
                        "text": {
                             "type": "mrkdwn",
                             "text": f"📝 *ARM Compatibility Analysis Summary for {github_url} *"
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": llm_summary # Assumes LLM returns markdown
                        }
                    }
                ]
                fallback_text = f"✅ ARM Compatibility Analysis Summary (LLM): {github_url}"
                logger.info("LLM summarization successful.")

            except Exception as llm_err:
                logger.error(f"LLM summarization failed: {llm_err}. Falling back to basic results format.", exc_info=True)
                # Fallback to the original formatting function if LLM fails
                result_blocks = format_analysis_results_blocks(
                    github_url, analysis_output["compatibility_result"]
                )
                fallback_text = f"⚠️ ARM 호환성 분석 결과 (LLM 실패): {github_url}"
                # Optionally add a notice about the LLM failure to the message
                result_blocks.append({"type": "divider"})
                result_blocks.append({
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f":warning: _LLM 요약 생성에 실패했습니다 ({type(llm_err).__name__}). 기본 분석 결과를 표시합니다._"}
                    ]
                })

        else:
            # --- Use Basic Formatting (LLM Disabled) ---
            logger.info("LLM disabled. Using basic results format.")
            result_blocks = format_analysis_results_blocks(
                github_url, analysis_output["compatibility_result"]
            )
            fallback_text = f"✅ ARM 호환성 분석 결과: {github_url}"


        # --- Send the Result Message ---
        if result_blocks:
            send_slack_block_message(
                client, channel_id, result_blocks, fallback_text, thread_ts=result_thread_ts
            )
        else:
            # Should not happen if error handling and fallbacks are correct, but just in case
            logger.error(f"Failed to generate any result blocks for {github_url}")
            send_slack_block_message(
                client, channel_id, [{"type": "section", "text": {"type": "mrkdwn", "text": "알 수 없는 오류로 분석 결과를 생성하지 못했습니다."}}], "Analysis Error", thread_ts=result_thread_ts
            )


    except Exception as analysis_error:
        # Catch unexpected errors during the check_compatibility call or result processing
        logger.exception(f"Critical error during analysis process for {github_url}: {analysis_error}")
        error_blocks = format_error_blocks(github_url, f"전체 분석 프로세스 실패: {analysis_error}")
        fallback_text = f"❌ 심각한 오류 발생 ({github_url})"
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
        return True

    text = event_data.get("text", "").lower()
    channel_id = event_data.get("channel")
    user_id = event_data.get("user")
    mention_message_ts = event_data.get("ts")
    original_thread_ts = event_data.get("thread_ts")
    target_thread_ts = original_thread_ts or mention_message_ts

    if not channel_id or not user_id or not mention_message_ts:
        logger.error(f"Missing crucial data in app_mention event: {event_data}")
        return False # Indicate processing failure

    github_url_pattern = r"https?://github\.com/[^/\s]+/[^/\s>\|]+"
    github_url_match = re.search(github_url_pattern, text)

    bot_user_id = client.auth_test().get("user_id", "bot") # Get bot's own user ID for mentions
    bot_name = f"<@{bot_user_id}>" # Use mention format

    if "analyze" in text or "분석" in text or "check" in text or "확인" in text:
        if github_url_match:
            github_url = github_url_match.group(0).rstrip(">")
            logger.info(f"AppMention: User {user_id} requested analysis for {github_url} in channel {channel_id}")
            trigger_arm_analysis(client, channel_id, github_url, thread_ts=target_thread_ts)
        else:
            logger.info(f"AppMention: User {user_id} requested analysis without URL in channel {channel_id}")
            missing_url_blocks = format_missing_url_blocks(user_id, bot_name) # Pass bot_name
            send_slack_block_message(
                client, channel_id, missing_url_blocks, "GitHub 레포지토리 URL을 제공해주세요.", thread_ts=target_thread_ts
            )
        return True # Handled


    elif "help" in text or "도움말" in text:
        logger.info(f"AppMention: User {user_id} requested help in channel {channel_id}")
        help_blocks = format_help_blocks(bot_name) # Pass bot_name
        send_slack_block_message(
            client, channel_id, help_blocks, "도움말 정보", thread_ts=target_thread_ts
        )
        return True # Handled

    else:
        logger.info(f"AppMention: User {user_id} sent unknown command in channel {channel_id}")
        unknown_blocks = format_unknown_command_blocks(user_id, bot_name) # Pass bot_name
        send_slack_block_message(
            client, channel_id, unknown_blocks, "알 수 없는 명령어", thread_ts=target_thread_ts
        )
        return True # Handled (acknowledged as unknown)


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

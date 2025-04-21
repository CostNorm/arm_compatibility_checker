import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Dict, Any, Optional
import json  # For potential debug formatting

logger = logging.getLogger(__name__)

# --- Slack API Interaction Helpers ---


def send_slack_block_message(
    client: WebClient,
    channel_id: str,
    blocks: List[Dict[str, Any]],
    text: str = "Notification",  # Fallback text for notifications
    thread_ts: Optional[str] = None,
) -> Optional[str]:
    """
    Sends a block message to a Slack channel or user and returns the message timestamp (ts).

    Args:
        client: The initialized Slack WebClient.
        channel_id: The ID of the channel or user to send the message to.
        blocks: A list of Slack Block Kit blocks.
        text: Fallback text for notifications.
        thread_ts: The timestamp of the parent message to reply in a thread.

    Returns:
        The timestamp (ts) of the sent message, or None if sending failed.
    """
    if not client:
        logger.error("Slack client is not initialized. Cannot send message.")
        return None
    try:
        response = client.chat_postMessage(
            channel=channel_id, blocks=blocks, text=text, thread_ts=thread_ts
        )
        ts = response.get("ts")
        logger.info(f"Message sent to {channel_id} (Thread: {thread_ts}). TS: {ts}")
        return ts
    except SlackApiError as e:
        logger.error(
            f"Error sending Slack message to {channel_id} (Thread: {thread_ts}): {e.response['error']}",
            exc_info=True,  # Include stack trace for API errors
        )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error sending Slack message to {channel_id} (Thread: {thread_ts}): {e}",
            exc_info=True,
        )
        return None


def update_slack_message(
    client: WebClient,
    channel_id: str,
    ts: str,
    blocks: List[Dict[str, Any]],
    text: str = "Updated Notification",  # Fallback text
) -> bool:
    """
    Updates an existing Slack message using its timestamp (ts).

    Args:
        client: The initialized Slack WebClient.
        channel_id: The ID of the channel containing the message.
        ts: The timestamp (ts) of the message to update.
        blocks: The new list of Slack Block Kit blocks.
        text: New fallback text for notifications.

    Returns:
        True if the message was updated successfully, False otherwise.
    """
    if not client:
        logger.error("Slack client is not initialized. Cannot update message.")
        return False
    if not ts:
        logger.error("Cannot update message: Timestamp (ts) is missing.")
        return False
    try:
        response = client.chat_update(
            channel=channel_id, ts=ts, blocks=blocks, text=text
        )
        logger.info(f"Message {ts} in channel {channel_id} updated successfully.")
        return response.get("ok", False)
    except SlackApiError as e:
        logger.error(
            f"Error updating Slack message {ts} in {channel_id}: {e.response['error']}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error updating Slack message {ts} in {channel_id}: {e}",
            exc_info=True,
        )
        return False


# --- Block Kit Formatting Helpers ---


def _get_repo_display_name(github_url: str) -> str:
    """Extracts 'owner/repo' from a GitHub URL for display."""
    try:
        # More robust extraction
        path_parts = github_url.strip().rstrip("/").split("/")
        if len(path_parts) >= 2 and "github.com" in path_parts[-3].lower():
            owner = path_parts[-2]
            repo = path_parts[-1].replace(".git", "")
            return f"`{owner}/{repo}`"
    except Exception:
        pass  # Fallback if parsing fails
    return f"`{github_url}`"  # Fallback to showing the full URL


def format_ack_blocks(github_url: str) -> List[Dict[str, Any]]:
    """Formats an acknowledgment message."""
    repo_display = _get_repo_display_name(github_url)
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⏳ Analysis request received for {repo_display}. Starting analysis...",
            },
        }
    ]


def format_error_blocks(
    github_url: Optional[str], error_message: Any
) -> List[Dict[str, Any]]:
    """Formats an error message."""
    repo_display = (
        _get_repo_display_name(github_url) if github_url else "the requested repository"
    )
    error_text = f"❌ *Error during ARM Compatibility Analysis for {repo_display}*"
    # Format error details in a code block for readability
    detail_text = f"```\n{str(error_message)}\n```"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": error_text}},
        {"type": "section", "text": {"type": "mrkdwn", "text": detail_text}},
    ]


def format_help_blocks(bot_mention_name: str = "@ARMCompatBot") -> List[Dict[str, Any]]:
    """Formats the help message."""
    # Use the actual mention name passed in
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*ARM Compatibility Bot Usage*"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Mention me with the `analyze` command followed by a GitHub repository URL:\n"
                f"• `{bot_mention_name} analyze https://github.com/owner/repo`\n\n"
                f"Or ask for help:\n"
                f"• `{bot_mention_name} help`",
            },
        },
    ]


def format_unknown_command_blocks(
    user_id: str, bot_mention_name: str = "@ARMCompatBot"
) -> List[Dict[str, Any]]:
    """Formats the unknown command message."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Hi <@{user_id}>! Sorry, I didn't understand that command. Try `{bot_mention_name} help` to see what I can do.",
            },
        }
    ]


def format_missing_url_blocks(
    user_id: str, bot_mention_name: str = "@ARMCompatBot"
) -> List[Dict[str, Any]]:
    """Formats a message indicating a missing URL when requesting analysis."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{user_id}>, please provide the GitHub repository URL after the `analyze` command.\n"
                f"Example: `{bot_mention_name} analyze https://github.com/owner/repository`",
            },
        }
    ]


def format_llm_summary_blocks(
    github_url: str, llm_summary_markdown: str
) -> List[Dict[str, Any]]:
    """
    Formats the LLM summary into Slack blocks, splitting long summaries
    to respect Slack's 3000 character limit for text blocks.
    """
    # Define Slack's character limit for section text blocks
    SLACK_SECTION_TEXT_LIMIT = 3000

    repo_display = _get_repo_display_name(github_url)
    # Ensure summary is not empty
    summary_content = (
        llm_summary_markdown.strip()
        if llm_summary_markdown
        else "_LLM summary could not be generated or was empty._"
    )

    # Initial blocks (Title)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📝 *ARM Compatibility Analysis Summary for {repo_display}*",
            },
        },
        {"type": "divider"},
    ]

    # Split the summary content if it exceeds the limit
    if len(summary_content) <= SLACK_SECTION_TEXT_LIMIT:
        # Fits in one block
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary_content},
            }
        )
    else:
        # Needs splitting
        logger.info(
            f"LLM summary exceeds {SLACK_SECTION_TEXT_LIMIT} chars, splitting into multiple blocks."
        )
        start_index = 0
        while start_index < len(summary_content):
            # Find the best split point (prefer newline before limit)
            end_index = start_index + SLACK_SECTION_TEXT_LIMIT
            if end_index >= len(summary_content):
                # Last chunk
                chunk = summary_content[start_index:]
                end_index = len(summary_content)  # Ensure loop terminates
            else:
                # Try to find a newline near the end_index to split cleanly
                split_pos = summary_content.rfind("\n", start_index, end_index)
                if split_pos != -1 and split_pos > start_index:
                    # Found a newline to split at
                    chunk = summary_content[start_index:split_pos]
                    end_index = split_pos + 1  # Start next chunk after newline
                else:
                    # No newline found, split at the limit
                    chunk = summary_content[start_index:end_index]
                    # end_index remains the same

            if chunk.strip():  # Avoid adding empty blocks
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": chunk},
                    }
                )
            start_index = end_index  # Move to the next chunk

            # Add a divider between chunks if there are more
            if start_index < len(summary_content):
                blocks.append({"type": "divider"})

    return blocks


def format_analysis_results_blocks(
    github_url: str, analysis_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Formats the structured compatibility results into Slack blocks (Fallback if LLM fails).
    Adapts to the new analysis_result structure.
    """
    blocks = []
    repo_display = _get_repo_display_name(github_url)

    # --- Overall Summary ---
    overall_compatibility = analysis_result.get("overall_compatibility", "unknown")
    icon = (
        "✅"
        if overall_compatibility == "compatible"
        else "❓" if overall_compatibility == "unknown" else "❌"
    )
    summary_text = f"{icon} *ARM Compatibility Analysis for {repo_display}: {overall_compatibility.capitalize()}*"
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": summary_text}})

    # --- Recommendations ---
    recommendations = analysis_result.get("recommendations", [])
    if recommendations:
        # Limit number of recommendations shown directly for brevity
        max_recs = 7
        rec_items = [f"• {rec}" for rec in recommendations[:max_recs]]
        if len(recommendations) > max_recs:
            rec_items.append(f"• _... ({len(recommendations) - max_recs} more)_")

        rec_text = "*Recommendations:*\n" + "\n".join(rec_items)
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": rec_text}})

    # --- Analysis Details (Brief Summary) ---
    analysis_details = analysis_result.get("analysis_details", {})
    context = analysis_result.get("context", {})
    stats = context.get("statistics", {})
    enabled_analyzers = context.get("enabled_analyzers", [])

    details_texts = []
    if stats:
        details_texts.append(
            f"Found {stats.get('incompatible_items', 0)} incompatible, "
            f"{stats.get('compatible_items', 0)} compatible, and "
            f"{stats.get('unknown_items', 0)} unknown/partial items."
        )

    # Briefly mention findings per enabled analyzer
    for analyzer_name in enabled_analyzers:
        # Map analyzer name back to the key used in analysis_details
        key_map = {
            "terraform": "instance_types",
            "docker": "docker_images",
            "dependency": "dependencies",
        }
        analysis_key = key_map.get(analyzer_name)
        if analysis_key and analysis_key in analysis_details:
            results_list = analysis_details[analysis_key].get("results", [])
            if results_list:
                issues = [
                    item for item in results_list if item.get("compatible") is not True
                ]
                if issues:
                    details_texts.append(
                        f"_{analyzer_name.capitalize()}: {len(issues)} potential issue(s) found._"
                    )
                else:
                    details_texts.append(
                        f"_{analyzer_name.capitalize()}: No compatibility issues found._"
                    )
            elif analysis_details[analysis_key].get("error"):
                details_texts.append(
                    f"_{analyzer_name.capitalize()}: Error during analysis._"
                )

    if details_texts:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": " | ".join(details_texts)}],
            }
        )

    # Add a note that this is a fallback format
    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": ":warning: _Displaying basic analysis results (LLM summary failed or disabled)._",
                }
            ],
        }
    )

    return blocks

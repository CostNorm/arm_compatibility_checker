# slack_bot/slack_utils.py
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Dict, Any, Optional

logger = logging.getLogger()

def send_slack_block_message(
    client: WebClient,
    channel_id: str,
    blocks: List[Dict[str, Any]],
    text: str = "Notification",
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
        logger.info(
            f"Message sent to {channel_id} (Thread: {thread_ts}). TS: {response.get('ts')}"
        )
        return response.get("ts")
    except SlackApiError as e:
        logger.error(
            f"Error sending Slack message to {channel_id} (Thread: {thread_ts}): {e.response['error']}"
        )
        return None


# Removed open_slack_modal as it's no longer used


def update_slack_message(
    client: WebClient,
    channel_id: str,
    ts: str,
    blocks: List[Dict[str, Any]],
    text: str = "Updated Notification",
) -> bool:
    """
    Updates an existing Slack message.

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
    try:
        response = client.chat_update(
            channel=channel_id, ts=ts, blocks=blocks, text=text
        )
        logger.info(f"Message {ts} in channel {channel_id} updated successfully.")
        return response.get("ok", False)
    except SlackApiError as e:
        logger.error(
            f"Error updating Slack message {ts} in {channel_id}: {e.response['error']}"
        )
        return False


# --- Formatting Helpers (Optional but Recommended) ---


def format_analysis_results_blocks(
    github_url: str, compatibility_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Formats the compatibility results into Slack blocks."""
    suggestions = []
    # Extract repo name from GitHub URL (e.g., 'owner/repo' from 'https://github.com/owner/repo')
    repo_display = f"`{'/'.join(github_url.rstrip('/').split('/')[-2:])}`"

    # Determine overall status and icon
    overall_compatibility = compatibility_result.get("overall_compatibility", "unknown")
    icon = (
        "✅"
        if overall_compatibility == "compatible"
        else "❓" if overall_compatibility == "unknown" else "❌"
    )
    summary_text = f"{icon} *ARM Compatibility Analysis for {repo_display}: {overall_compatibility.capitalize()}*"
    print(f"summary_text: {summary_text}")
    suggestions.append(
        {"type": "section", "text": {"type": "mrkdwn", "text": summary_text}}
    )

    # Add recommendations if any
    recommendations = compatibility_result.get("recommendations", [])
    if recommendations:
        rec_text = "*Recommendations:*\n" + "\n".join(
            [f"• {rec}" for rec in recommendations]
        )
        suggestions.append({"type": "divider"})
        suggestions.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": rec_text}}
        )

    # Add details about specific findings (optional, can make messages long)
    details_added = False
    details_text = "*Analysis Details:*\n"

    instance_types = [
        item
        for item in compatibility_result.get("instance_types", [])
        if item.get("compatible") is not True
    ]
    if instance_types:
        details_added = True
        details_text += f"_{len(instance_types)} Instance Type issues found:_\n"
        details_text += "\n".join(
            [
                f"  - `{item.get('current', 'N/A')}` in `{item.get('file', 'N/A').split('/')[-1]}`: {item.get('reason', 'No details')}"
                for item in instance_types[:3]
            ]
        )  # Limit details
        if len(instance_types) > 3:
            details_text += "\n  _... (and more)_"
        details_text += "\n"

    docker_images = [
        item
        for item in compatibility_result.get("docker_images", [])
        if item.get("compatible") is not True
    ]
    if docker_images:
        details_added = True
        details_text += f"_{len(docker_images)} Docker Image issues found:_\n"
        details_text += "\n".join(
            [
                f"  - `{item.get('image', 'N/A')}` in `{item.get('file', 'N/A').split('/')[-1]}`: {item.get('reason', 'No details')}"
                for item in docker_images[:3]
            ]
        )  # Limit details
        if len(docker_images) > 3:
            details_text += "\n  _... (and more)_"
        details_text += "\n"

    dependencies = [
        item
        for item in compatibility_result.get("dependencies", [])
        if item.get("compatible") is not True
    ]
    if dependencies:
        details_added = True
        details_text += f"_{len(dependencies)} Dependency issues found:_\n"
        # Be careful with potentially long reasons
        details_text += "\n".join(
            [
                f"  - `{item.get('dependency', item.get('name', 'N/A'))}` in `{item.get('file', 'N/A').split('/')[-1]}` (Direct: {item.get('direct', '?')})"
                for item in dependencies[:3]
            ]
        )  # Limit details
        if len(dependencies) > 3:
            details_text += "\n  _... (and more)_"
        details_text += "\n"

    if details_added:
        suggestions.append({"type": "divider"})
        suggestions.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": details_text}}
        )

    return suggestions


def format_error_blocks(github_url: str, error: Any) -> List[Dict[str, Any]]:
    """Formats an error message into Slack blocks."""

    repo_display = (
        f"`{'/'.join(github_url.rstrip('/').split('/')[-2:])}`"
        if github_url
        else "the requested repository"
    )
    error_text = f"❌ *Error during ARM Compatibility Analysis for {repo_display}*"
    detail_text = f"```{str(error)}```"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": error_text}},
        {"type": "section", "text": {"type": "mrkdwn", "text": detail_text}},
    ]


def format_ack_blocks(github_url: str) -> List[Dict[str, Any]]:
    """Formats an acknowledgment message into Slack blocks."""
    # Extract repo name from GitHub URL (e.g., 'owner/repo' from 'https://github.com/owner/repo')
    repo_display = f"`{'/'.join(github_url.rstrip('/').split('/')[-2:])}`"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⏳ Analysis request received for {repo_display}. Starting analysis...",
            },
        }
    ]


def format_help_blocks(bot_name: str = "bot") -> List[Dict[str, Any]]:
    """Formats the help message into Slack blocks."""
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*ARM Compatibility Bot Usage*"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"• `@{bot_name} analyze https://github.com/user/repo`\n• `@{bot_name} help`",
            },
        },
    ]


def format_unknown_command_blocks(
    user_id: str, bot_name: str = "bot"
) -> List[Dict[str, Any]]:
    """Formats the unknown command message."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{user_id}> Sorry, I didn't understand that. Try `@{bot_name} help`.",
            },
        }
    ]


# Removed format_ask_for_repo_blocks


def format_missing_url_blocks(
    user_id: str, bot_name: str = "bot"
) -> List[Dict[str, Any]]:
    """Formats a message indicating a missing URL when requesting analysis."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{user_id}> Please provide the GitHub repository URL directly after the command, like this:\n`@{bot_name} analyze https://github.com/owner/repository`",
            },
        }
    ]


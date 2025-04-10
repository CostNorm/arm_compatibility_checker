import logging
import re
from typing import Dict, Any, Optional, Tuple
from slack_sdk.web import WebClient
from analysis_orchestrator import AnalysisOrchestrator
from services.llm_service import LLMService
from slack.utils import (
    format_ack_blocks,
    format_error_blocks,
    format_help_blocks,
    format_analysis_results_blocks,
    send_slack_block_message,
    update_slack_message,
    format_llm_summary_blocks,
    format_missing_url_blocks,
    format_unknown_command_blocks,
)

logger = logging.getLogger(__name__)


class SlackHandler:
    """
    Handles incoming Slack events, parses commands, and orchestrates compatibility analysis.
    """

    def __init__(self, orchestrator: AnalysisOrchestrator, llm_service: LLMService):
        """
        Initializes the SlackHandler with required services.

        Args:
            orchestrator: An instance of the AnalysisOrchestrator.
            llm_service: An instance of the LLMService.
        """
        self.orchestrator = orchestrator
        self.llm_service = llm_service

    def _parse_command(
        self, event_data: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Parses the command and arguments from a Slack event.
        Handles different event types like app_mention and message.

        Args:
            event_data: The event data dictionary from Slack.

        Returns:
            A tuple containing:
            - command: The extracted command (e.g., 'analyze', 'help').
            - args: The arguments provided with the command.
            Returns (None, None) if parsing fails or is not applicable.
        """
        event_type = event_data.get("type")
        text = event_data.get("text", "")

        if event_type == "app_mention":
            # For mentions, text starts with <@Uxxxxxxx>
            # Remove the mention part to get the actual command
            mention_pattern = r"<@\w+>\s*(.*)"
            match = re.match(mention_pattern, text)
            if match:
                command_text = match.group(1).strip()
                parts = command_text.split(maxsplit=1)
                command = parts[0].lower() if parts else None
                args = parts[1] if len(parts) > 1 else None
                return command, args
        elif event_type == "message":
            # For direct messages or messages in channels (less common for commands)
            # Check if the message starts with a potential command keyword
            # This part might need refinement based on how you expect users to interact in DMs
            parts = text.strip().split(maxsplit=1)
            if len(parts) > 0:
                command = parts[
                    0
                ].lower()  # Consider a specific prefix or structure for DM commands
                args = parts[1] if len(parts) > 1 else None
                # Example: If expecting "analyze <url>" in DMs
                if command in ["analyze", "help"]:  # Only recognize specific commands
                    return command, args

        # If parsing fails or event type is not handled
        return None, None

    def handle_interaction(self, body: Dict[str, Any], client: WebClient) -> bool:
        """
        Handles Slack interactions (events and potentially actions).

        Args:
            body: The parsed payload from the Slack event.
            client: The Slack WebClient instance.

        Returns:
            True if the interaction was processed successfully (even if resulting in an error message),
            False if a critical error occurred that requires retrying the SQS message.
        """
        event_type = body.get("type")
        if event_type == "event_callback":
            event_data = body.get("event", {})
            event_subtype = event_data.get("type")

            # Skip retries and bot's own messages
            if event_data.get("bot_id"):
                return True  # Acknowledge bot's own message, don't process
            if event_data.get("subtype") == "bot_message":
                return True  # Acknowledge message from another bot

            # Handle mentions and direct messages
            if event_subtype == "app_mention" or event_subtype == "message":
                # Extract command and arguments
                command, args = self._parse_command(event_data)
                channel_id = event_data.get("channel")
                user_id = event_data.get("user")
                bot_user_id = client.auth_test().get(
                    "user_id", "bot"
                )  # Get bot's own user ID for mentions
                bot_name = f"{bot_user_id}"  # Use mention format
                thread_ts = event_data.get(
                    "ts"
                )  # Use the message timestamp as thread identifier

                if not command:
                    # If no command recognized, maybe send a generic help message or ignore
                    logger.warning(
                        f"Could not parse command from event: {event_data.get('event_id')}"
                    )
                    # Send a generic help message in a thread
                    help_blocks = format_help_blocks(
                        f"<@{bot_name}>"
                    )  # Mention the bot_name
                    send_slack_block_message(
                        client, channel_id, help_blocks, "Help Message", thread_ts
                    )
                    return True  # Processed the event, even if it was just help

                # --- Command Routing ---
                if command == "analyze":
                    # Acknowledge the request immediately
                    ack_blocks = format_ack_blocks(
                        args if args else "repository"
                    )  # Use URL if available
                    ack_response = send_slack_block_message(
                        client, channel_id, ack_blocks, "Analysis Started", thread_ts
                    )
                    message_ts = (
                        ack_response  # Use the timestamp of the ack message for updates
                    )

                    if not args:
                        error_blocks = format_missing_url_blocks(user_id)
                        update_slack_message(
                            client,
                            channel_id,
                            message_ts,
                            error_blocks,
                            "Error: Missing URL",
                        )
                        return True  # Processed, but with error

                    repo_url = args.strip().strip("<>")

                    try:
                        # Trigger the analysis
                        analysis_result = self.orchestrator.analyze_repository(repo_url)

                        # Check for errors during analysis
                        if "error" in analysis_result:
                            error_blocks = format_error_blocks(
                                repo_url, analysis_result["error"]
                            )
                            update_slack_message(
                                client,
                                channel_id,
                                message_ts,
                                error_blocks,
                                "Analysis Failed",
                            )
                            return True  # Processed, but with error

                        logger.info(
                            f"Analysis completed for {repo_url}: {analysis_result}"
                        )

                        # Format and send the results
                        # Try generating LLM summary first
                        llm_summary = self.llm_service.summarize_analysis(
                            analysis_result
                        )
                        if llm_summary:
                            summary_blocks = format_llm_summary_blocks(
                                repo_url, llm_summary
                            )
                            update_slack_message(
                                client,
                                channel_id,
                                message_ts,
                                summary_blocks,
                                "Analysis Complete (LLM Summary)",
                            )
                        else:
                            # Fallback to basic formatting if LLM fails or is disabled
                            logger.warning(
                                "LLM summary generation failed or is disabled. Using basic formatting."
                            )
                            basic_blocks = format_analysis_results_blocks(
                                repo_url, analysis_result
                            )
                            update_slack_message(
                                client,
                                channel_id,
                                message_ts,
                                basic_blocks,
                                "Analysis Complete",
                            )

                        return True  # Successfully processed

                    except Exception as e:
                        # Catch unexpected errors during the analysis process
                        logger.exception(
                            f"Critical error during analysis for {repo_url}: {e}"
                        )
                        error_blocks = format_error_blocks(repo_url, str(e))
                        update_slack_message(
                            client,
                            channel_id,
                            message_ts,
                            error_blocks,
                            "Analysis Failed",
                        )
                        return True  # Processed, but with error

                elif command == "help":
                    # Send help message
                    help_blocks = format_help_blocks(
                        f"<@{bot_name}>"
                    )  # Mention the bot_name
                    send_slack_block_message(
                        client, channel_id, help_blocks, "Help Information", thread_ts
                    )
                    return True  # Processed successfully

                else:
                    # Unknown command
                    unknown_blocks = format_unknown_command_blocks(user_id)
                    send_slack_block_message(
                        client, channel_id, unknown_blocks, "Unknown Command", thread_ts
                    )
                    return True  # Processed, but with error message

        # Handle other event types or interaction types (e.g., button clicks) if needed
        elif event_type == "interactive_message":  # Example for button clicks
            logger.info("Received interactive message event (button click, etc.)")
            # Parse payload, identify action, and handle accordingly
            # ...
            return True  # Assume processed for now

        # Default case for unhandled event types
        logger.warning(f"Unhandled event type received: {event_type}")
        return True  # Acknowledge receipt, but don't process further

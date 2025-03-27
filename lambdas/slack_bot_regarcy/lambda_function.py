import os
import sys
import json
import urllib.parse
import logging
import boto3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import re  # Import re at the top

# Import your custom functions
# Ensure check_compatibility is available
from slack_bot_regarcy import check_compatibility

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
else:
    logger.error("SLACK_BOT_OAUTH_TOKEN environment variable not set!")

# --- Helper Functions (using slack_sdk) ---


def send_slack_block_message(
    client: WebClient,
    channel_id: str,
    blocks: list,
    text: str = "Notification",
    thread_ts: str = None,
) -> str | None:
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
        logger.error("Slack client not initialized.")
        return None
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text=text,  # Fallback text
            thread_ts=thread_ts,  # Add this to reply in thread
        )
        return response.get("ts")  # Return the timestamp
    except SlackApiError as e:
        logger.error(
            f"Error sending Slack message to {channel_id} (Thread: {thread_ts}): {e.response['error']}"
        )
        return None


def notify_arm_suggestions(
    client: WebClient, channel_id: str, suggestions: list, thread_ts: str = None
):
    """
    Formats and sends ARM compatibility suggestions to Slack, potentially in a thread.

    Args:
        client: The initialized Slack WebClient.
        channel_id: The ID of the channel or user.
        suggestions: A list of suggestion strings (markdown formatted).
        thread_ts: The timestamp of the parent message to reply in a thread.
    """
    if not client:
        logger.error("Slack client not initialized.")
        return None

    if not suggestions:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "✅ 분석 결과, 특별한 ARM 호환성 문제가 발견되지 않았습니다.",
                },
            }
        ]
        text = "ARM Compatibility: No issues found."
    else:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚙️ ARM 호환성 분석 결과",
                    "emoji": True,
                },
            }
        ]
        for suggestion in suggestions:
            blocks.append({"type": "divider"})
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": suggestion}}
            )
        text = "ARM Compatibility Analysis Results"  # Fallback text

    # Use send_slack_block_message to handle sending and potential threading
    send_slack_block_message(client, channel_id, blocks, text, thread_ts=thread_ts)


def open_github_repo_modal(client: WebClient, trigger_id: str):
    """Displays the GitHub repository URL input modal using slack_sdk."""
    if not client:
        logger.error("Slack client not initialized.")
        return None

    modal_view = {
        "type": "modal",
        "callback_id": "github_repo_modal",
        "title": {"type": "plain_text", "text": "GitHub 저장소 분석"},
        "submit": {"type": "plain_text", "text": "분석하기"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "ARM 호환성을 분석할 GitHub 저장소 URL을 입력해주세요.",
                },
            },
            {
                "type": "input",
                "block_id": "github_url_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "github_url_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "예: https://github.com/사용자명/저장소명",
                    },
                },
                "label": {"type": "plain_text", "text": "GitHub 저장소 URL"},
            },
        ],
    }

    try:
        response = client.views_open(trigger_id=trigger_id, view=modal_view)
        return response
    except SlackApiError as e:
        logger.error(f"Error opening Slack modal: {e.response['error']}")
        return None


# --- Main Lambda Handler ---


def lambda_handler(event, context):
    if not slack_client:
        logger.error("Slack client is not available. Check SLACK_BOT_OAUTH_TOKEN.")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Slack client not initialized"}),
        }

    if not SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL environment variable not set!")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "SQS_QUEUE_URL not configured"}),
        }

    logger.info(f"Received event: {json.dumps(event)}")

    for record in event.get("Records", []):
        receipt_handle = record.get("receiptHandle")
        message_processed = False
        ack_message_ts = (
            None  # Initialize ack message timestamp for potential threading
        )

        try:
            sqs_body_str = record.get("body")
            if not sqs_body_str:
                logger.warning("SQS record has no body.")
                message_processed = True
                continue

            original_request_payload = json.loads(sqs_body_str)
            headers = original_request_payload.get("headers", {})
            if headers.get("x-slack-retry-num"):
                logger.info(
                    f"Slack retry detected (Attempt {headers.get('x-slack-retry-num')}). Ignoring message."
                )
                message_processed = True
                continue

            body_str = original_request_payload.get("body", "")
            if not body_str:
                logger.warning("Original request payload has no 'body' field.")
                message_processed = True
                continue

            if "payload=" in body_str and body_str.startswith("payload="):
                parsed_qs = urllib.parse.parse_qs(body_str)
                payload_str = parsed_qs.get("payload", [None])[0]
                body = json.loads(payload_str) if payload_str else {}
            else:
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON body: {body_str[:200]}...")
                    body = {}

            logger.info(f"Parsed Slack body type: {body.get('type')}")

            slack_event_type = body.get("type")

            # --- Interaction Handling ---
            if slack_event_type == "view_submission":
                view_payload = body.get("view", {})
                callback_id = view_payload.get("callback_id")

                if callback_id == "github_repo_modal":
                    state_values = view_payload.get("state", {}).get("values", {})
                    github_url = (
                        state_values.get("github_url_block", {})
                        .get("github_url_input", {})
                        .get("value")
                    )
                    user_id = body.get("user", {}).get("id")

                    if github_url and user_id:
                        # Send ack message to user via DM and get its timestamp
                        ack_blocks = [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"⏳ 분석 요청 접수: `{github_url}`. 분석을 시작합니다...",
                                },
                            }
                        ]
                        ack_message_ts = send_slack_block_message(
                            slack_client, user_id, ack_blocks, "분석 시작..."
                        )

                        # Perform the analysis
                        try:
                            compatibility_results = check_compatibility(github_url)
                            # Send results back to user via DM, threaded to the ack message if possible
                            notify_arm_suggestions(
                                slack_client,
                                user_id,
                                compatibility_results.get("suggestions", []),
                                thread_ts=ack_message_ts,
                            )
                        except Exception as analysis_error:
                            logger.error(
                                f"Error during check_compatibility for {github_url}: {analysis_error}"
                            )
                            error_blocks = [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"❌ `{github_url}` 분석 중 오류 발생: {analysis_error}",
                                    },
                                }
                            ]
                            # Send error in thread if ack message was sent
                            send_slack_block_message(
                                slack_client,
                                user_id,
                                error_blocks,
                                f"오류: {github_url} 분석 실패",
                                thread_ts=ack_message_ts,
                            )

                        message_processed = True
                    else:
                        logger.warning(
                            "Missing github_url or user_id in modal submission."
                        )
                        message_processed = True

            elif slack_event_type == "block_actions":
                actions = body.get("actions", [])
                trigger_id = body.get("trigger_id")
                for action in actions:
                    if (
                        action.get("action_id") == "open_github_repo_modal"
                        and trigger_id
                    ):
                        open_github_repo_modal(slack_client, trigger_id)
                        message_processed = True
                        break

            # --- Event Handling ---
            elif slack_event_type == "event_callback":
                event_data = body.get("event", {})
                event_subtype = event_data.get("type")

                if event_subtype == "app_mention":
                    if event_data.get("bot_id"):
                        message_processed = True
                        continue

                    text = event_data.get("text", "").lower()
                    channel = event_data.get("channel")
                    user = event_data.get("user")
                    # thread_ts from the original mention event, if it was in a thread
                    original_thread_ts = event_data.get("thread_ts")
                    # ts of the mention message itself, useful if NOT replying to the mention directly
                    # but rather starting a *new* thread from the mention
                    mention_message_ts = event_data.get("ts")

                    github_url_pattern = r"https?://github\.com/[^/\s]+/[^/\s>]+"
                    github_url_match = re.search(github_url_pattern, text)

                    # --- Define target thread ---
                    # Generally, we want to reply to the *mention message itself*
                    # unless the mention was *already* in a thread, in which case we continue that thread.
                    target_thread_ts = original_thread_ts or mention_message_ts

                    if "분석" in text or "체크" in text or "확인" in text:
                        if github_url_match:
                            github_url = github_url_match.group(0).rstrip(">")
                            ack_blocks = [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"⏳ 분석 요청 접수: `{github_url}`. 분석을 시작합니다...",
                                    },
                                }
                            ]
                            # Send ack message IN THE SAME THREAD as the mention
                            ack_message_ts = send_slack_block_message(
                                slack_client,
                                channel,
                                ack_blocks,
                                "분석 시작...",
                                thread_ts=target_thread_ts,
                            )

                            # Perform analysis
                            try:
                                compatibility_results = check_compatibility(github_url)
                                # Reply to the ACK message (which is already in the target thread)
                                notify_arm_suggestions(
                                    slack_client,
                                    channel,
                                    compatibility_results.get("suggestions", []),
                                    thread_ts=ack_message_ts or target_thread_ts,
                                )  # Fallback just in case
                            except Exception as analysis_error:
                                logger.error(
                                    f"Error during check_compatibility for {github_url}: {analysis_error}"
                                )
                                error_blocks = [
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": f"❌ `{github_url}` 분석 중 오류 발생: {analysis_error}",
                                        },
                                    }
                                ]
                                # Reply to the ACK message (which is already in the target thread)
                                send_slack_block_message(
                                    slack_client,
                                    channel,
                                    error_blocks,
                                    f"오류: {github_url} 분석 실패",
                                    thread_ts=ack_message_ts or target_thread_ts,
                                )  # Fallback

                            message_processed = True

                        else:
                            # Ask for URL via button -> modal (send this message in the mention's thread)
                            repo_input_blocks = [
                                {
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"<@{user}> ARM 호환성을 분석할 GitHub 저장소를 입력해주세요.",
                                    },
                                },
                                {
                                    "type": "actions",
                                    "elements": [
                                        {
                                            "type": "button",
                                            "text": {
                                                "type": "plain_text",
                                                "text": "저장소 URL 입력",
                                                "emoji": True,
                                            },
                                            "action_id": "open_github_repo_modal",
                                        }
                                    ],
                                },
                            ]
                            send_slack_block_message(
                                slack_client,
                                channel,
                                repo_input_blocks,
                                "Input GitHub Repo URL",
                                thread_ts=target_thread_ts,
                            )
                            message_processed = True

                    elif "도움말" in text or "help" in text:
                        help_blocks = [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "*ARM 호환성 분석 봇 사용법*",
                                },
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "• `@<bot_name> 분석 https://github.com/사용자/저장소`\n• `@<bot_name> 분석`\n• `@<bot_name> 도움말`",
                                },
                            },
                        ]
                        # Send help in the mention's thread
                        send_slack_block_message(
                            slack_client,
                            channel,
                            help_blocks,
                            "Help",
                            thread_ts=target_thread_ts,
                        )
                        message_processed = True

                    else:
                        instruction_blocks = [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"<@{user}> 명령어를 인식할 수 없습니다. `@<bot_name> 도움말`을 입력해보세요.",
                                },
                            }
                        ]
                        # Send instructions in the mention's thread
                        send_slack_block_message(
                            slack_client,
                            channel,
                            instruction_blocks,
                            "Unknown command",
                            thread_ts=target_thread_ts,
                        )
                        message_processed = True

        except json.JSONDecodeError as json_err:
            logger.error(
                f"JSON Decode Error processing SQS message: {json_err}. Message body: {sqs_body_str[:500]}"
            )
        except Exception as e:
            logger.exception(f"Error processing SQS message: {e}")

        finally:
            if message_processed and receipt_handle:
                try:
                    sqs.delete_message(
                        QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle
                    )
                    logger.info(
                        f"Successfully processed and deleted message: {receipt_handle}"
                    )
                except Exception as del_err:
                    logger.error(
                        f"Error deleting message {receipt_handle} from SQS: {del_err}"
                    )
            elif not receipt_handle:
                logger.warning(
                    "No receipt handle found for SQS message, cannot delete."
                )
            else:
                logger.warning(
                    f"Message {receipt_handle} not processed successfully or error occurred, will not delete."
                )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": f'Processed {len(event.get("Records", []))} records.'}
        ),
    }

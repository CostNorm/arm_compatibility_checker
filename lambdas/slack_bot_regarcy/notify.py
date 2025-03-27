import os
import json
import requests


def send_slack_block_message(
    webhook_url_or_channel: str, blocks: list, text: str = None
):
    """
    Slack API를 사용하여 블록 형식의 메시지를 전송합니다.

    Args:
        webhook_url_or_channel: Slack Webhook URL 또는 채널 ID
        blocks: Slack 블록 형식의 메시지 (리스트)
        text: 블록이 지원되지 않는 클라이언트를 위한 대체 텍스트
    """
    print("\n\n1\n\n")

    # webhook URL인지 채널 ID인지 확인
    if webhook_url_or_channel.startswith("http"):
        # Webhook URL인 경우 직접 요청 전송
        response = requests.post(
            webhook_url_or_channel,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"blocks": blocks, "text": text or "ARM 호환성 분석 결과"}),
        )
        return response.status_code == 200
    else:
        print("\n\n2\n\n")
        # 채널 ID인 경우 Slack API 사용
        slack_token = os.environ.get("SLACK_BOT_OAUTH_TOKEN")

        if not slack_token:
            print("SLACK_TOKEN이 설정되지 않았습니다.")
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {slack_token}",
        }
        print("\n\n3\n\n")

        payload = {"channel": webhook_url_or_channel, "blocks": blocks}
        print(f"payload: {payload}")

        if text:
            payload["text"] = text

        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            data=json.dumps(payload),
        )
        print(response.text)

        return response.status_code == 200


def notify_arm_suggestions(webhook_url_or_channel, suggestions):
    """
    ARM호환성 관련 제안사항을 Slack으로 알리고, 상세 내용을 Thread에 추가합니다.

    Args:
        webhook_url_or_channel: Slack Webhook URL 또는 채널 ID
        suggestions: ARM호환성 제안사항 목록
    """

    # Webhook URL은 Slack Thread를 지원하지 않으므로 처리 필요
    if webhook_url_or_channel.startswith("http"):
        print("Webhook URL은 스레드를 지원하지 않습니다. 채널 ID를 사용하세요.")
        return False

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "ARM호환성 관련 제안사항",
                "emoji": True,
            },
        },
        {"type": "divider"},
    ]

    for idx, suggestion in enumerate(suggestions, 1):
        preview = suggestion if len(suggestion) <= 150 else suggestion[:150] + "…"
        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{idx}. {preview}*"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "_자세한 내용은 이 메시지의 스레드를 확인하세요._",
                        }
                    ],
                },
                {"type": "divider"},
            ]
        )

    slack_token = os.environ.get("SLACK_BOT_OAUTH_TOKEN")
    if not slack_token:
        print("SLACK_BOT_OAUTH_TOKEN이 설정되지 않았습니다.")
        return False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {slack_token}",
    }

    payload = {
        "channel": webhook_url_or_channel,
        "blocks": blocks,
        "text": "ARM호환성 관련 제안사항",
    }

    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers=headers,
        data=json.dumps(payload),
    )

    result = response.json()

    if not result.get("ok"):
        print(f"메시지 전송 실패: {result}")
        return False

    thread_ts = result["ts"]

    # 상세내용을 thread에 추가
    for idx, detail in enumerate(suggestions, 1):
        thread_text = f"*{idx}번 제안 상세 내용:*\n{detail}"
        thread_payload = {
            "channel": webhook_url_or_channel,
            "text": thread_text,
            "thread_ts": thread_ts,
        }

        thread_response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            data=json.dumps(thread_payload),
        )

        thread_result = thread_response.json()
        if not thread_result.get("ok"):
            print(f"{idx}번 상세내용 thread 전송 실패: {thread_result}")
            return False

    return True


def send_slack_thread_message(channel_id, thread_ts, text=None, blocks=None):
    """
    Slack 메시지 스레드에 답글을 전송합니다.

    Args:
        channel_id: Slack 채널 ID
        thread_ts: 원본 메시지의 timestamp(thread ID)
        text: 전송할 메시지 내용 (blocks가 지원되지 않는 클라이언트를 위한 대체 텍스트)
        blocks: Slack 블록 형식의 메시지 (리스트)
    """
    slack_token = os.environ.get("SLACK_BOT_OAUTH_TOKEN")

    if not slack_token:
        print("SLACK_BOT_OAUTH_TOKEN이 설정되지 않았습니다.")
        return False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {slack_token}",
    }

    payload = {"channel": channel_id, "thread_ts": thread_ts}

    if text:
        payload["text"] = text

    if blocks:
        payload["blocks"] = blocks

    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers=headers,
        data=json.dumps(payload),
    )

    print(response.text)

    return response.status_code == 200


def notify_arm_suggestions_with_threads(channel_id, suggestions):
    """
    ARM호환성 관련 제안사항을 Slack으로 전송하고, 상세 내용을 thread로 추가합니다.

    Args:
        channel_id: Slack 채널 ID (Webhook URL은 thread 사용 불가능)
        suggestions: ARM호환성 제안사항 목록
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "ARM호환성 관련 제안사항",
                "emoji": True,
            },
        },
        {"type": "divider"},
    ]

    short_previews = []

    for idx, suggestion in enumerate(suggestions, 1):
        preview = suggestion if len(suggestion) <= 150 else suggestion[:150] + "…"
        short_previews.append(preview)
        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{idx}. {preview}*"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "_자세한 내용은 이 메시지의 스레드를 확인하세요._",
                        }
                    ],
                },
                {"type": "divider"},
            ]
        )

    # 최초 메시지 전송 후 timestamp 받아오기
    slack_token = os.environ.get("SLACK_BOT_OAUTH_TOKEN")

    if not slack_token:
        print("SLACK_BOT_OAUTH_TOKEN이 설정되지 않았습니다.")
        return False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {slack_token}",
    }

    payload = {
        "channel": channel_id,
        "blocks": blocks,
        "text": "ARM호환성 관련 제안사항",
    }

    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers=headers,
        data=json.dumps(payload),
    )

    result = response.json()

    if not result.get("ok"):
        print(f"메시지 전송 실패: {result}")
        return False

    thread_ts = result["ts"]  # 첫 메시지의 timestamp를 thread ID로 사용

    # 상세내용을 thread에 개별 전송 (블록 형식 활용)
    for idx, detail in enumerate(suggestions, 1):
        # 상세 내용을 보기 좋게 포맷팅
        thread_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{idx}번 상세 내용",
                    "emoji": True,
                },
            },
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": detail}},
        ]

        # 백업용 텍스트 (블록이 지원되지 않는 클라이언트용)
        fallback_text = f"*{idx}번 상세 내용:*\n{detail}"

        success = send_slack_thread_message(
            channel_id, thread_ts, text=fallback_text, blocks=thread_blocks
        )

        if not success:
            print(f"{idx}번 상세내용 thread 전송 실패")
            return False

    return True

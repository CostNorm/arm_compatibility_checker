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
    ARM호환성 관련 제안사항을 Slack으로 알립니다.

    Args:
        webhook_url_or_channel: Slack Webhook URL 또는 채널 ID
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

    for suggestion in suggestions:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": suggestion}}
        )

    return send_slack_block_message(
        webhook_url_or_channel, blocks, "ARM호환성 관련 제안사항"
    )

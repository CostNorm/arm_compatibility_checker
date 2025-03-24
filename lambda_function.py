import os, sys, json, urllib.parse


from slack_bot import (
    send_slack_block_message,
    notify_arm_suggestions,
    check_compatibility,
)

# Slack 알림 설정: Slack Webhook URL (환경변수로 설정)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#arm-chatbot-testing")  # 현재 사용되지 않음
SLACK_BOT_OAUTH_TOKEN = os.getenv("SLACK_BOT_OAUTH_TOKEN")


def open_github_repo_modal(trigger_id):
    """
    사용자에게 GitHub 저장소 URL 입력 모달을 표시합니다.

    Args:
        trigger_id: 모달을 트리거하기 위한 ID
    """
    import requests

    modal_json = {
        "trigger_id": trigger_id,
        "view": {
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
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SLACK_BOT_OAUTH_TOKEN}",
    }

    response = requests.post(
        "https://slack.com/api/views.open", headers=headers, data=json.dumps(modal_json)
    )

    return response.json()


def lambda_handler(event, context):
    try:
        # 환경변수 확인
        if not SLACK_WEBHOOK_URL:
            raise ValueError("SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다.")

        if not SLACK_BOT_OAUTH_TOKEN:
            raise ValueError("SLACK_BOT_OAUTH_TOKEN 환경변수가 설정되지 않았습니다.")

        # body로 들어온 값을 확인
        # body = json.loads(event["body"])
        body_str = event.get("body", "")
        # URL 인코딩된 payload인지 확인
        if "payload=" in body_str:
            parsed_body = urllib.parse.parse_qs(body_str)
            # payload 값은 리스트로 반환됨
            payload_str = parsed_body.get("payload", [None])[0]
            if payload_str:
                body = json.loads(payload_str)
            else:
                body = {}
        else:
            body = json.loads(body_str)

        # print(f"body : {body}")
        # debug_message = f"*람다 함수 호출 - 수신된 event:*\n```{json.dumps(event["body"], indent=2, ensure_ascii=False)}```"
        # debug_suggestions = [debug_message]
        # notify_arm_suggestions(body["event"].get("channel"), debug_suggestions)

        # Slack 이벤트 타입 확인
        # Slack 이벤트 시스템의 URL 검증 요청 처리
        if body.get("type") == "url_verification":
            return {
                "statusCode": 200,
                "body": json.dumps({"challenge": body.get("challenge")}),
            }

        # 인터랙티브 요청 처리 (모달 제출)
        if body.get("type") == "view_submission":
            view_payload = body.get("view", {})
            callback_id = view_payload.get("callback_id")

            if callback_id == "github_repo_modal":
                # 모달에서 입력된 GitHub URL 가져오기
                state_values = view_payload.get("state", {}).get("values", {})
                github_url = (
                    state_values.get("github_url_block", {})
                    .get("github_url_input", {})
                    .get("value")
                )

                if github_url:
                    # 사용자 정보 가져오기
                    user_id = body.get("user", {}).get("id")

                    # 처리 중임을 알리는 메시지를 DM으로 전송
                    dm_blocks = [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{github_url} 저장소의 ARM 호환성을 분석 중입니다... 잠시만 기다려주세요.",
                            },
                        }
                    ]
                    # DM으로 메시지 전송
                    send_slack_block_message(user_id, dm_blocks)

                    # ARM 호환성 확인 (백그라운드 처리 대신 직접 처리)
                    compatibility_results = check_compatibility(github_url)

                    # 결과를 사용자에게 DM으로 전송
                    notify_arm_suggestions(
                        user_id, compatibility_results["suggestions"]
                    )

                # 모달 제출 처리 완료
                return {
                    "statusCode": 200,
                    "body": json.dumps({}),  # 빈 응답으로 모달 닫기
                }

        # Slack 이벤트 메시지 처리
        if body.get("event") and body["event"].get("type") == "app_mention":
            # 봇에 멘션된 메시지 처리
            text = body["event"].get("text", "").lower()
            channel = body["event"].get("channel")
            user = body["event"].get("user")
            trigger_id = body.get("trigger_id")

            # 명령어 기반 처리
            if "분석" in text or "체크" in text or "확인" in text:
                # GitHub URL 직접 포함 여부 확인
                import re

                github_url_pattern = r"https?://github\.com/[^/\s]+/[^/\s>]+"
                github_url_match = re.search(github_url_pattern, text)

                if github_url_match:
                    # URL이 포함된 경우 직접 분석
                    github_url = github_url_match.group(0)

                    # 처리 중임을 알리는 메시지 전송
                    processing_blocks = [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{github_url} 저장소의 ARM 호환성을 분석 중입니다... 잠시만 기다려주세요.",
                            },
                        }
                    ]
                    send_slack_block_message(channel, processing_blocks)

                    # ARM 호환성 확인
                    compatibility_results = check_compatibility(github_url)

                    # 결과를 Slack에 전송
                    notify_arm_suggestions(
                        channel, compatibility_results["suggestions"]
                    )

                    return {
                        "statusCode": 200,
                        "body": json.dumps(
                            {"message": "ARM 호환성 검사가 완료되었습니다."}
                        ),
                    }
                else:
                    # URL이 포함되지 않은 경우 입력 폼 제공
                    # 사용자에게 URL 입력 버튼 제공
                    repo_input_blocks = [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "ARM 호환성을 분석할 GitHub 저장소를 입력해주세요.",
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
                                    "value": "open_github_repo_modal",
                                    "action_id": "open_github_repo_modal",
                                }
                            ],
                        },
                    ]
                    send_slack_block_message(channel, repo_input_blocks)

                    return {
                        "statusCode": 200,
                        "body": json.dumps(
                            {"message": "GitHub 저장소 URL 입력 양식을 전송했습니다."}
                        ),
                    }

            elif "도움말" in text or "help" in text:
                # 도움말 메시지 전송
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
                            "text": "• `@arm-bot 분석 https://github.com/사용자/저장소` - 지정한 GitHub 저장소의 ARM 호환성 분석\n• `@arm-bot 분석` - 저장소 URL 입력 양식 표시\n• `@arm-bot 도움말` - 이 도움말 표시",
                        },
                    },
                ]
                send_slack_block_message(channel, help_blocks)

                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "도움말이 전송되었습니다."}),
                }
            else:
                # 인식할 수 없는 명령어인 경우 안내 메시지 전송
                instruction_blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "명령어를 인식할 수 없습니다. 다음 명령어를 사용해보세요:\n• `@arm-bot 분석 https://github.com/사용자/저장소`\n• `@arm-bot 분석`\n• `@arm-bot 도움말`",
                        },
                    }
                ]
                send_slack_block_message(channel, instruction_blocks)

                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "안내 메시지가 전송되었습니다."}),
                }

        # 인터랙티브 컴포넌트 처리 (버튼 클릭)
        if body.get("type") == "block_actions":
            # 버튼 클릭 등의 액션 처리
            actions = body.get("actions", [])
            for action in actions:
                if action.get("action_id") == "open_github_repo_modal":
                    # 모달 열기
                    trigger_id = body.get("trigger_id")
                    open_github_repo_modal(trigger_id)

                    return {
                        "statusCode": 200,
                        "body": json.dumps({"message": "모달이 열렸습니다."}),
                    }

        # 기존 제안사항 처리 로직 유지 (호환성)
        elif "github_url" in body:
            # ARM 호환성 확인
            github_url = body["github_url"].strip()
            compatibility_results = check_compatibility(github_url)

            # 결과를 Slack에 전송
            notify_arm_suggestions(
                SLACK_WEBHOOK_URL, compatibility_results["suggestions"]
            )

            return {
                "statusCode": 200,
                "body": json.dumps({"message": "ARM 호환성 검사가 완료되었습니다."}),
            }
        elif "suggestions" in body:
            # 기존 로직: 이미 생성된 제안사항을 처리
            notify_arm_suggestions(SLACK_WEBHOOK_URL, body["suggestions"])

            return {
                "statusCode": 200,
                "body": json.dumps({"message": "알림이 성공적으로 전송되었습니다."}),
            }
        else:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"message": "GitHub 저장소 URL 또는 제안사항이 필요합니다."}
                ),
            }

    except Exception as e:
        print(f"오류 발생: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": str(e)}),
        }

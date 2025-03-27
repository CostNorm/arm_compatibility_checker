import json
import os
import logging
import boto3
import time
import hmac
import hashlib
import base64
import uuid

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")


def validate_slack_signature(event):
    """
    Slack 서명을 검증하는 함수.
    - 헤더에서 'X-Slack-Signature'와 'X-Slack-Request-Timestamp'를 추출합니다.
    - 요청 타임스탬프가 현재 시간과 5분(300초) 이내인지 확인합니다.
    - 요청 본문(body)와 타임스탬프를 사용하여 서명을 재계산하고,
      헤더의 서명과 일치하는지 검증합니다.

    검증에 성공하면 True, 실패하면 False를 반환합니다.
    """
    headers = event.get("headers", {})
    slack_signature = headers.get("x-slack-signature", "")
    slack_request_timestamp = headers.get("x-slack-request-timestamp", "")

    if not slack_signature or not slack_request_timestamp:
        logger.error("Missing Slack signature or timestamp in headers.")
        return False

    # 타임스탬프 검증 (요청이 5분 이내인지 확인)
    current_ts = int(time.time())
    try:
        req_ts = int(slack_request_timestamp)
    except ValueError:
        logger.error("Invalid timestamp format.")
        return False

    if abs(current_ts - req_ts) > 300:  # 5분 = 300초
        logger.error("Request timestamp is out of the allowed range.")
        return False

    # 요청 본문(body) 추출 및 디코딩 (isBase64Encoded가 True이면 base64 디코딩)
    body = event.get("body", "")
    if event.get("isBase64Encoded", False):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception as e:
            logger.error(f"Error decoding base64 body: {e}")
            return False

    # Slack 서명 검증을 위한 base string 생성: "v0:{timestamp}:{body}"
    sig_basestring = f"v0:{slack_request_timestamp}:{body}"

    # HMAC-SHA256 방식으로 해시 계산
    computed_signature = (
        "v0="
        + hmac.new(
            SLACK_SIGNING_SECRET.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    # 서명 비교
    if not hmac.compare_digest(computed_signature, slack_signature):
        logger.error("Invalid Slack signature.")
        return False

    return True


def lambda_handler(event, context):
    """
    1) Slack/HTTP 이벤트를 수신한다.
    2) 별도의 함수(validate_slack_signature)를 통해 Slack 서명 검증을 진행한다.
       - 검증 성공 시 True, 실패 시 False를 반환한다.
    3) 검증이 완료되면 SQS Queue에 Message를 Send한다.
    4) 즉시 200 OK를 반환한다.
    """
    logger.info(f"Received event: {event}")

    # body = json.loads(event["body"])

    # # Challenge 요청을 확인하고 응답
    # if "challenge" in body:
    #     return {"statusCode": 200, "body": json.dumps({"challenge": body["challenge"]})}

    if not validate_slack_signature(event):
        return {
            "statusCode": 401,
            "body": {"message": "Bad Request: Invalid Slack signature or request."},
        }

    # SQS 메시지 발행
    client = boto3.client("sqs")
    message_to_send = json.dumps(event)

    try:
        response = client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=message_to_send,
        )
        logger.info(f"SQS SendMessage Response: {response}")
    except Exception as e:
        logger.error(f"Error publishing to SQS: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal Server Error"}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "OK"}),
        "response_type": "in_channel",
        "text": "처리를 시작합니다. 잠시만 기다려주세요!",
    }

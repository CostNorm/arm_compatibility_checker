# Slack 봇 AWS 배포 및 설정 가이드

이 가이드는 ARM 호환성 분석을 위한 Slack 봇을 AWS Lambda에 배포하고 Slack 워크스페이스에 앱으로 추가하는 방법을 설명합니다. 처음 시작하는 분들도 쉽게 따라할 수 있도록 상세히 설명되어 있습니다.

## 목차

1. [사전 준비사항](#사전-준비사항)
2. [Slack 앱 생성](#slack-앱-생성)
3. [AWS Lambda 함수 생성](#aws-lambda-함수-생성)
4. [코드 배포](#코드-배포)
5. [AWS API Gateway 설정](#aws-api-gateway-설정)
6. [Slack 앱 구성](#slack-앱-구성)
7. [환경 변수 설정](#환경-변수-설정)
8. [테스트 및 사용 방법](#테스트-및-사용-방법)
9. [문제 해결](#문제-해결)

## 사전 준비사항

- AWS 계정
- Slack 워크스페이스 관리자 권한
- Git (코드 다운로드용)
- Python 3.8 이상 (로컬 테스트용)
- AWS CLI (선택사항, 배포 자동화용)

## Slack 앱 생성

1. [Slack API 웹사이트](https://api.slack.com/apps)에 접속하여 로그인합니다.
2. "Create New App" 버튼을 클릭합니다.
3. "From scratch" 옵션을 선택합니다.
4. 앱 이름(예: "ARM 호환성 봇")을 입력하고 워크스페이스를 선택한 후 "Create App" 버튼을 클릭합니다.
5. 생성된 앱 페이지의 왼쪽 메뉴에서 "Basic Information"을 클릭하여 다음 정보를 기록해둡니다:
   - App ID
   - Client ID
   - Client Secret
   - Verification Token
   - Signing Secret

이 정보들은 나중에 환경 변수 설정 시 필요합니다.

## AWS Lambda 함수 생성

1. [AWS Lambda 콘솔](https://console.aws.amazon.com/lambda)에 로그인합니다.
2. "함수 생성" 버튼을 클릭합니다.
3. "새로 작성" 옵션을 선택합니다.
4. 다음 정보를 입력합니다:
   - 함수 이름: `slack-arm-bot` (원하는 이름으로 변경 가능)
   - 런타임: Python 3.9 (또는 그 이상)
   - 아키텍처: x86_64 (Lambda ARM 아키텍처를 사용하려면 x86_64 대신 arm64 선택)
   - 실행 역할: "기본 Lambda 권한을 가진 새 역할 생성" 선택
5. "함수 생성" 버튼을 클릭합니다.

## 코드 배포

### 방법 1: 콘솔을 통한 배포

1. 이 프로젝트의 코드를 로컬 컴퓨터에 다운로드합니다.
2. 터미널에서 다음 명령어를 실행하여 필요한 패키지를 포함한 배포 패키지를 생성합니다:

```bash
# 프로젝트 디렉토리로 이동
cd slack_bot

# 배포용 디렉토리 생성
mkdir deployment
cd deployment

# 필요한 패키지 설치
pip install -r ../requirements.txt -t .

# 프로젝트 파일 복사
cp ../*.py .
cp ../.env.example .env  # .env 파일을 적절히 수정해야 합니다

# 배포 ZIP 파일 생성
zip -r ../deployment.zip .

# 상위 디렉토리로 이동
cd ..
```

3. AWS Lambda 콘솔에서 생성한 함수로 이동합니다.
4. "코드" 탭에서 "업로드" 버튼을 클릭하고 "Zip 파일"을 선택합니다.
5. 위에서 생성한 `deployment.zip` 파일을 업로드합니다.
6. "저장" 버튼을 클릭합니다.

### 방법 2: AWS CLI를 통한 배포

1. AWS CLI가 이미 설치되어 있고 구성되어 있는지 확인합니다.
2. 터미널에서 다음 명령어를 실행합니다:

```bash
# 배포 패키지 생성 (위 방법 1의 1-2단계와 동일)

# Lambda 함수 업데이트
aws lambda update-function-code \
  --function-name slack-arm-bot \
  --zip-file fileb://deployment.zip
```

## AWS API Gateway 설정

1. [AWS API Gateway 콘솔](https://console.aws.amazon.com/apigateway)에 접속합니다.
2. "API 생성" 버튼을 클릭합니다.
3. "REST API" 카드에서 "구축"을 클릭합니다.
4. "새 API 생성"을 선택하고 API 이름을 "SlackBotAPI"로 입력한 후 "API 생성"을 클릭합니다.
5. "리소스 생성" 버튼을 클릭하고 다음 정보를 입력합니다:
   - 리소스 이름: "slack-events"
   - 리소스 경로: "/slack-events"
6. "리소스 생성" 버튼을 클릭합니다.
7. 새로 생성된 "/slack-events" 리소스를 선택하고 "메서드 생성" 버튼을 클릭합니다.
8. 드롭다운에서 "POST"를 선택하고 체크 표시를 클릭합니다.
9. 메서드 설정에서 다음 정보를 입력합니다:
   - 통합 유형: "Lambda 함수"
   - Lambda 프록시 통합 사용: 체크
   - Lambda 함수: 위에서 생성한 Lambda 함수 이름("slack-arm-bot")
10. "저장" 버튼을 클릭합니다.
11. "작업" 드롭다운 메뉴에서 "API 배포"를 선택합니다.
12. "배포 스테이지" 드롭다운에서 "New Stage"를 선택하고 스테이지 이름을 "prod"로 입력한 후 "배포"를 클릭합니다.
13. API가 배포되면 "스테이지 세부 정보"에서 "호출 URL"을 복사해둡니다. 이 URL은 다음 형식이어야 합니다:
    `https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod/slack-events`

## Slack 앱 구성

1. [Slack API 웹사이트](https://api.slack.com/apps)에서 만든 앱으로 이동합니다.

### 봇 사용자 추가

1. 왼쪽 메뉴에서 "OAuth & Permissions"를 클릭합니다.
2. "Bot Token Scopes" 섹션에서 "Add an OAuth Scope" 버튼을 클릭하고 다음 권한을 추가합니다:
   - `app_mentions:read` - 봇이 멘션된 메시지 읽기
   - `chat:write` - 메시지 보내기
   - `im:write` - DM 보내기
   - `chat:write.public` - 공개 채널에 메시지 보내기
   - `channels:read` - 채널 정보 읽기
   - `commands` - 슬래시 명령어 추가
3. 페이지 상단에서 "Install to Workspace" 버튼을 클릭하여 앱을 워크스페이스에 설치합니다.
4. 설치 후 표시되는 "Bot User OAuth Token"을 복사하여 기록해둡니다. 이 값은 `SLACK_TOKEN` 환경 변수에 사용됩니다.

### 이벤트 구독 설정

1. 왼쪽 메뉴에서 "Event Subscriptions"를 클릭합니다.
2. "Enable Events" 스위치를 켭니다.
3. "Request URL" 필드에 위에서 복사한 API Gateway URL을 입력합니다.
   - Slack은 URL에 확인 요청을 보내며, Lambda 함수가 올바르게 응답하면 체크 표시가 나타납니다.
4. "Subscribe to bot events" 섹션에서 "Add Bot User Event" 버튼을 클릭하고 `app_mention` 이벤트를 추가합니다.
5. 페이지 하단의 "Save Changes" 버튼을 클릭합니다.

### 인터랙티브 컴포넌트 설정

1. 왼쪽 메뉴에서 "Interactivity & Shortcuts"를 클릭합니다.
2. "Interactivity" 스위치를 켭니다.
3. "Request URL" 필드에 위에서 복사한 API Gateway URL을 입력합니다.
4. 페이지 하단의 "Save Changes" 버튼을 클릭합니다.

### Incoming Webhook 생성

1. 왼쪽 메뉴에서 "Incoming Webhooks"를 클릭합니다.
2. "Activate Incoming Webhooks" 스위치를 켭니다.
3. "Add New Webhook to Workspace" 버튼을 클릭합니다.
4. 봇이 메시지를 보낼 채널을 선택하고 "Allow" 버튼을 클릭합니다.
5. 생성된 Webhook URL을 복사하여 기록해둡니다. 이 값은 `SLACK_WEBHOOK_URL` 환경 변수에 사용됩니다.

## 환경 변수 설정

1. [AWS Lambda 콘솔](https://console.aws.amazon.com/lambda)에서 생성한 함수로 이동합니다.
2. "구성" 탭을 클릭하고 왼쪽 메뉴에서 "환경 변수"를 선택합니다.
3. "편집" 버튼을 클릭하고 다음 환경 변수를 추가합니다:

| 키                             | 값                   | 설명                                     |
| ------------------------------ | -------------------- | ---------------------------------------- |
| `SLACK_WEBHOOK_URL`            | Incoming Webhook URL | Slack에 메시지를 보내기 위한 Webhook URL |
| `SLACK_CHANNEL`                | #general             | (선택 사항) 기본 채널 이름 또는 ID       |
| `SLACK_BOT_OAUTH_TOKEN`        | Bot User OAuth Token | Slack API와 상호 작용하기 위한 봇 토큰   |
| `SLACK_BOT_APP_ID`             | App ID               | Slack App ID                             |
| `SLACK_BOT_CLIENT_ID`          | Client ID            | Slack Client ID                          |
| `SLACK_BOT_CLIENT_SECRET`      | Client Secret        | Slack Client Secret                      |
| `SLACK_BOT_VERIFICATION_TOKEN` | Verification Token   | Slack Verification Token                 |
| `GITHUB_TOKEN`                 | Github Token         | Github Token                             |

4. "저장" 버튼을 클릭합니다.

## 테스트 및 사용 방법

1. Slack 워크스페이스에서 봇을 채널에 초대합니다: `/invite @봇이름`
2. 다음 명령어를 사용하여 봇과 상호작용합니다:
   - `@봇이름 분석` - GitHub 저장소 URL 입력 양식(버튼) 표시
   - `@봇이름 분석 https://github.com/사용자명/저장소명` - URL 직접 분석
   - `@봇이름 도움말` - 도움말 표시

## 문제 해결

### Lambda 함수가 시간 초과됨

- Lambda 함수의 제한 시간을 늘립니다. "구성" -> "일반 구성" -> "편집"에서 제한 시간을 3분(180초) 또는 더 길게 설정합니다.

### API Gateway URL이 Slack에서 검증되지 않음

- Lambda 함수 코드가 올바르게 배포되었는지 확인합니다.
- API Gateway 설정이 올바른지 확인합니다.
- Lambda 함수 로그를 확인하여 오류를 파악합니다.

### 봇이 메시지에 응답하지 않음

- 환경 변수가 올바르게 설정되었는지 확인합니다.
- Slack 앱에 필요한 권한이 모두 부여되었는지 확인합니다.
- Lambda 함수 로그를 확인하여 오류를 파악합니다.

### 모달 창이 열리지 않음

- `SLACK_TOKEN` 환경 변수가 올바르게 설정되었는지 확인합니다.
- 봇에 `chat:write` 및 관련 권한이 있는지 확인합니다.

로그를 확인하려면 [AWS CloudWatch 콘솔](https://console.aws.amazon.com/cloudwatch)에서 "로그" -> "로그 그룹"으로 이동한 다음, `/aws/lambda/slack-arm-bot` 로그 그룹을 확인하세요.

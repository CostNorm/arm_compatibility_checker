# arm-bot

1. 명령어 기반 처리:
   @arm-bot 분석 - GitHub 저장소 URL 입력 양식(버튼) 표시
   @arm-bot 분석 <https://github.com/>... - URL 직접 분석
   @arm-bot 도움말 - 도움말 표시
2. 인터랙티브 컴포넌트:
   버튼: "저장소 URL 입력" 버튼 클릭 시 모달 표시
   모달: 저장소 URL을 입력할 수 있는 양식 제공
3. 워크플로우:
   사용자가 @arm-bot 분석 명령어 입력
   봇이 "저장소 URL 입력" 버튼이 포함된 메시지 전송
   사용자가 버튼 클릭
   모달 창이 열리고 사용자가 GitHub URL 입력
   사용자가 "분석하기" 버튼 클릭
   봇이 URL의 ARM 호환성 분석 후 결과를 DM으로 전송

---

이 구현은 Slack의 인터랙티브 기능을 활용하여 사용자 경험을 개선한 것입니다. 사용자가 직접 URL을 입력하는 대신 직관적인 폼을 통해 입력할 수 있습니다.
Lambda 함수를 배포할 때는 다음 환경 변수가 필요합니다:

- SLACK_WEBHOOK_URL: Slack 알림을 보내기 위한 Webhook URL
- SLACK_TOKEN: Slack API를 사용하기 위한 봇 토큰 (인터랙티브 컴포넌트에 필수)
- SLACK_CHANNEL: (선택사항) 기본 채널 ID

  또한 Slack 앱 설정에서 다음 권한과 기능을 활성화해야 합니다:

1. Interactivity & Shortcuts: 인터랙티브 기능 활성화
2. Event Subscriptions: app_mention 이벤트 구독
3. Bot Token Scopes: chat:write, im:write 등 필요한 권한 추가

## TODO

- llm 기능은 현재 기능 동작 파악 간편화를 위해 사용안했음.

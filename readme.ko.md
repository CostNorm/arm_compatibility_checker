# ARM 호환성 봇 (Slack용)

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) <!-- 선택적 라이선스 배지 -->

## README 언어 선택

- [한국어 번역](readme.ko.md)
- [English](readme.md)

## 개요

ARM 호환성 봇은 개발자 및 운영팀이 GitHub 리포지토리의 ARM64 호환성을 평가하는 데 도움을 주기 위해 설계된 Slack 애플리케이션입니다. 이는 특히 AWS Graviton 프로세서와 같은 ARM 기반 컴퓨팅 플랫폼으로 마이그레이션을 계획할 때 유용합니다.

봇은 Slack에서 명령어를 수신하여 지정된 GitHub 리포지토리를 가져오고, 다양한 설정 및 의존성 파일을 분석한 후, 잠재적인 호환성 문제를 Slack 스레드에 직접 보고합니다. 선택적으로 AWS Bedrock 언어 모델(LLM)을 활용하여 분석 결과에 대한 가독성 높은 요약을 제공할 수 있습니다.

## 주요 기능

- **Slack 연동:** Slack 내에서 멘션(`@ARMCompatBot analyze ...`)을 사용하여 봇과 직접 상호 작용합니다.
- **GitHub 리포지토리 분석:** GitHub API를 통해 리포지토리 콘텐츠를 가져옵니다.
- **모듈식 분석기:** 다음 요소들의 분석을 지원합니다:
  - **Terraform (`.tf`):** EC2 인스턴스 유형을 확인하고 ARM 기반 대안(예: Graviton `t4g`, `m6g`, `c7g` 등)을 제안합니다.
  - **Docker (`Dockerfile`):** 베이스 이미지를 검사하여 알려진 ARM 호환성 또는 멀티 아키텍처 지원 여부를 확인합니다.
  - **의존성:**
    - **Python (`requirements.txt`):** PyPI API 데이터 및 외부 `arm64-python-wheel-tester` 결과를 사용하여 네이티브 코드 컴파일 문제에 대해 PyPI 패키지를 확인합니다.
    - **JavaScript (`package.json`):** 휴리스틱 및 npm 레지스트리를 사용하여 네이티브 의존성(`node-gyp`, 알려진 문제 패키지)에 대해 npm 패키지를 확인합니다.
- **설정 가능한 분석:** 환경 변수를 통해 특정 분석기를 쉽게 활성화하거나 비활성화할 수 있습니다.
- **LLM 요약 (선택 사항):** AWS Bedrock(예: Claude 3 Sonnet/Haiku)을 사용하여 분석 결과 및 권장 사항에 대한 자연어 요약을 제공합니다.
- **비동기 처리:** AWS SQS를 사용하여 Slack 요청 처리와 잠재적으로 오래 실행될 수 있는 분석 작업을 분리하여 Slack의 3초 타임아웃 요구 사항을 충족합니다.
- **보안:** Slack 요청 서명을 확인하여 요청이 Slack에서 온 것인지 확인합니다.
- **확장성:** 새로운 분석기를 쉽게 추가할 수 있도록 인터페이스와 명확한 관심사 분리를 통해 설계되었습니다.

## 아키텍처

봇은 AWS 기반의 서버리스 아키텍처를 활용합니다:

```
+---------+      +-----------------+      +-------------+      +-------------------------+      +----------+
|  Slack  |<---->| API Gateway     |<---->| SQS Queue   |<---->| ARMCompatibilityBot     |<---->|  GitHub  |
| (사용자)|      | (게이트웨이 람다)|      |             |      | (처리 람다)             |      |   API    |
+---------+      +-----------------+      +-------------+      +-------------------------+      +----------+
     ^                                                             |          ^
     |                                                             |          | LLM 요약
     |-------------------------------------------------------------+          v
                                                                      +---------------+
                                                                      | AWS Bedrock   |
                                                                      | (LLM 서비스)  |
                                                                      +---------------+
```

1. **Slack:** 사용자는 멘션(`@ARMCompatBot analyze <repo_url>`)을 통해 봇과 상호 작용합니다.
2. **API Gateway (게이트웨이 람다):** Slack으로부터 HTTPS 요청을 수신합니다.
   - `SLACK_SIGNING_SECRET`을 사용하여 Slack 요청 서명을 확인합니다.
   - 필요한 경우 초기 Slack challenge 핸드셰이크를 수행합니다.
   - 유효한 경우 전체 Slack 이벤트 페이로드를 SQS 대기열에 넣습니다.
   - Slack의 3초 요구 사항을 충족하기 위해 즉시 `200 OK` 응답을 반환합니다.
3. **SQS 대기열:** 게이트웨이와 주요 처리 로직을 분리하는 버퍼 역할을 합니다. Slack 재시도를 처리하고 잠재적으로 더 긴 분석 시간을 허용합니다.
4. **ARMCompatibilityBot (처리 람다):**
   - SQS 대기열의 새 메시지에 의해 트리거됩니다.
   - SQS 메시지에서 Slack 이벤트를 파싱합니다 (`sqs_processor.py`).
   - 핵심 서비스(`GithubService`, `LLMService`)와 `AnalysisOrchestrator`를 초기화합니다.
   - `SlackHandler`가 명령어(`analyze` 또는 `help`)를 처리합니다.
   - `analyze` 명령어인 경우:
     - Slack 스레드에 확인 메시지를 보냅니다.
     - `AnalysisOrchestrator`는 `GithubService`를 사용하여 리포지토리 데이터를 가져옵니다.
     - 관련 파일들은 _활성화된_ `Analyzer`(Terraform, Docker, Dependency)로 전달됩니다.
     - 분석기는 검사(예: 인스턴스 유형, 베이스 이미지, 패키지 호환성)를 수행합니다.
     - 결과가 집계됩니다.
     - (선택 사항) `LLMService`가 AWS Bedrock을 사용하여 결과를 요약합니다.
     - `SlackHandler`는 `slack/utils.py`를 사용하여 결과(LLM 요약 또는 구조화된 데이터)를 포맷합니다.
     - 확인 메시지를 업데이트하여 최종 결과 메시지가 원래 Slack 스레드에 게시됩니다.
5. **GitHub API:** `GithubService`가 리포지토리 정보 및 파일 내용을 가져오는 데 사용됩니다.
6. **AWS Bedrock:** `LLMService`가 분석 요약을 생성하는 데 사용됩니다.

## 설정 및 배포

### 사전 요구 사항

- AWS 계정
- 로컬에 설치된 Python 3.9 이상
- 적절한 권한(SQS, Lambda, IAM, CloudWatch Logs, Bedrock)으로 구성된 AWS CLI
- AWS SAM CLI (배포 권장) 또는 유사한 서버리스 배포 도구
- Slack 워크스페이스 및 Slack 앱 생성 권한
- `repo` 범위(리포지토리 읽기 접근 권한)를 가진 GitHub 개인 액세스 토큰(PAT)

### 단계

1. **Slack 앱 생성:**

   - [api.slack.com/apps](https://api.slack.com/apps)로 이동하여 새 앱을 만듭니다.
   - **기능 및 설정 추가:**
     - **Bots:** 봇 사용자를 추가합니다.
     - **Event Subscriptions:**
       - 이벤트 활성화.
       - _봇 이벤트 구독:_ `app_mention`을 추가합니다.
       - 요청 URL 필드에는 배포 _후_ API Gateway URL이 필요합니다. Slack은 게이트웨이 람다가 처리해야 하는 challenge 요청을 이 URL로 보냅니다.
     - **권한 (OAuth & Permissions):**
       - 다음 봇 토큰 범위를 추가합니다:
         - `app_mentions:read` (멘션 수신용)
         - `chat:write` (메시지 게시용)
         - `commands` (선택 사항: 나중에 슬래시 명령어를 추가할 계획이 있는 경우)
       - 앱을 워크스페이스에 설치합니다.
   - **기록해 둘 것:**
     - "OAuth & Permissions" 페이지의 `SLACK_BOT_TOKEN` (`xoxb-`로 시작).
     - "Basic Information" 페이지의 `SLACK_SIGNING_SECRET`.

2. **GitHub 토큰 생성:**

   - GitHub 설정 -> 개발자 설정 -> 개인 액세스 토큰 -> Tokens (classic)으로 이동합니다.
   - `repo` 범위(또는 공개 리포지토리만 분석하는 경우 `public_repo`)를 가진 새 토큰을 생성합니다.
   - **기록해 둘 것:** 생성된 `GITHUB_TOKEN`. **비밀번호처럼 취급하세요.**

3. **환경 변수 설정:**

   - 로컬 개발을 위해 `ARMCompatibilityBot/src` 디렉토리의 *루트*에 `.env` 파일을 생성합니다 (이 파일은 Git에 커밋하면 **안 됩니다**).
   - 필요한 값으로 채웁니다 (아래 [설정](#설정) 섹션 참조).
   - 배포 시에는 이러한 변수들을 람다 함수 설정에서 직접 설정해야 합니다 (해당되는 경우 게이트웨이 람다와 처리 람다 모두).

4. **AWS SAM을 사용한 배포 (권장):**

   - `template.yaml` 파일이 필요합니다 (코드 스니펫에는 제공되지 않았지만 SAM의 표준입니다). 이 템플릿은 다음을 정의해야 합니다:
     - SQS 대기열.
     - 람다용 IAM 역할 (SQS, CloudWatch, 인터넷을 통한 GitHub 접근, Bedrock `InvokeModel` 권한).
     - **게이트웨이 람다 함수** (`slack_bot_gateway/lambda_function.py`):
       - API Gateway (HTTP API 권장)에 의해 트리거됩니다.
       - 환경 변수: `SQS_QUEUE_URL`, `SLACK_SIGNING_SECRET`.
     - **처리 람다 함수** (`ARMCompatibilityBot/src/lambda_function.py`):
       - SQS 대기열에 의해 트리거됩니다.
       - 환경 변수: [설정](#설정) 섹션에 나열된 모든 변수 (`SQS_QUEUE_URL` 포함).
       - 잠재적인 네트워크 호출 및 분석 복잡성으로 인해 적절한 메모리 크기(예: 512MB 이상)와 제한 시간(예: 1-5분)을 설정합니다.
   - `sam build` 및 `sam deploy --guided`를 실행합니다.

5. **Slack 이벤트 구독 URL 업데이트:**

   - 배포 후 API Gateway 호출 URL을 복사합니다.
   - Slack 앱 설정 -> Event Subscriptions로 돌아갑니다.
   - "Request URL" 필드에 URL을 붙여넣습니다. Slack이 `url_verification` 요청을 보낼 것입니다. 게이트웨이 람다는 이 challenge를 처리해야 하며 Slack은 "Verified"를 표시해야 합니다.
   - 변경 사항을 저장합니다.

6. **채널에 봇 초대:** 사용하려는 Slack 채널에 `@ARMCompatBot`(또는 설정한 이름)을 초대합니다.

## 사용법

봇이 초대된 채널 또는 다이렉트 메시지를 통해 봇과 상호 작용합니다:

1. **리포지토리 분석:**

   ```slack
   @ARMCompatBot analyze https://github.com/owner/repo-name
   ```

   `https://github.com/owner/repo-name`을 분석하려는 실제 공개 또는 비공개(GitHub 토큰이 접근 권한을 가진 경우) 리포지토리 URL로 바꿉니다.

2. **도움말 보기:**

   ```slack
   @ARMCompatBot help
   ```

봇은 먼저 스레드에 확인 메시지를 게시한 다음, 완료되면 해당 메시지를 분석 결과 또는 LLM 요약으로 업데이트합니다. 오류가 발생하면 스레드에 보고됩니다.

## 설정

봇은 설정을 위해 환경 변수를 사용합니다. 이는 주로 `config.py`에서 관리되며 다양한 모듈에서 접근합니다.

| 변수                         | `src/config.py` | 게이트웨이 람다 | 설명                                                                                                      | 기본값           |  필수  |
| :--------------------------- | :-------------: | :-------------: | :-------------------------------------------------------------------------------------------------------- | :--------------- | :----: |
| `GITHUB_TOKEN`               |       ✅        |       ❌        | `repo` 범위를 가진 GitHub 개인 액세스 토큰.                                                               | `""`             |   ✅   |
| `SLACK_BOT_TOKEN`            |       ✅        |       ❌        | Slack 봇 토큰 (`xoxb-`로 시작).                                                                           | `""`             |   ✅   |
| `SLACK_SIGNING_SECRET`       |       ✅        |       ✅        | Slack 앱 서명 비밀키. 게이트웨이가 요청을 확인하는 데 사용됩니다.                                         | `""`             |   ✅   |
| `SQS_QUEUE_URL`              |       ✅        |       ✅        | 요청 버퍼링에 사용되는 SQS 대기열의 URL.                                                                  | `None`           |   ✅   |
| `ENABLE_LLM`                 |       ✅        |       ❌        | LLM 요약을 활성화하려면 `True`, 아니면 `False`로 설정.                                                    | `True`           |   No   |
| `BEDROCK_REGION`             |       ✅        |       ❌        | Bedrock을 사용할 수 있는 AWS 리전 (예: `us-east-1`). `ENABLE_LLM`이 `True`인 경우 필요합니다.             | `us-east-1`      | If LLM |
| `BEDROCK_MODEL_ID`           |       ✅        |       ❌        | Bedrock 모델 ID (예: `anthropic.claude-3-sonnet-20240229-v1:0`). `ENABLE_LLM`이 `True`인 경우 필요합니다. | `config.py` 참조 | If LLM |
| `LLM_LANGUAGE`               |       ✅        |       ❌        | LLM 프롬프트 및 응답 언어 (예: `english`, `korean`).                                                      | `english`        |   No   |
| `ENABLE_TERRAFORM_ANALYZER`  |       ✅        |       ❌        | Terraform 분석기를 활성화하려면 `True`로 설정.                                                            | `False`          |   No   |
| `ENABLE_DOCKER_ANALYZER`     |       ✅        |       ❌        | Docker 분석기를 활성화하려면 `True`로 설정.                                                               | `False`          |   No   |
| `ENABLE_DEPENDENCY_ANALYZER` |       ✅        |       ❌        | 의존성 분석기(Python & JS)를 활성화하려면 `True`로 설정.                                                  | `True`           |   No   |
| `LOG_LEVEL`                  |       ✅        |       ✅        | 애플리케이션 로깅 레벨 (예: `INFO`, `DEBUG`, `WARNING`).                                                  | `INFO`           |   No   |

_(참고: 로컬 개발 중 `.env` 파일이 존재하면 `python-dotenv`가 이를 로드하는 데 사용됩니다.)_

## 코드 구조

```
├── src/                        # 처리 람다용 메인 소스 코드
│   ├── analysis_orchestrator.py # 분석 프로세스 조정
│   ├── config.py               # 설정 로드 및 제공
│   ├── lambda_function.py      # SQS 메시지 처리를 위한 AWS 람다 핸들러
│   ├── sqs_processor.py        # SQS 메시지 본문 파싱하여 Slack 이벤트 가져오기
│   │
│   ├── analyzers/              # 특정 분석 모듈용 코드
│   │   ├── __init__.py
│   │   ├── base_analyzer.py    # 분석기용 추상 기본 클래스
│   │   ├── docker_analyzer.py  # Dockerfile 분석
│   │   ├── terraform_analyzer.py # Terraform 인스턴스 유형 분석
│   │   └── dependency_analyzer/ # 소프트웨어 의존성 분석
│   │       ├── __init__.py
│   │       ├── base_checker.py # 의존성 검사기용 추상 기본 클래스
│   │       ├── js_checker.py   # Node.js (package.json) 의존성 검사
│   │       ├── manager.py      # 다른 의존성 검사기 관리
│   │       └── python_checker.py # Python (requirements.txt) 의존성 검사
│   │
│   ├── core/                   # 핵심 인터페이스 또는 공유 컴포넌트
│   │   └── interfaces.py       # Analyzer 및 DependencyChecker 인터페이스 정의
│   │
│   ├── services/               # 외부 API와 상호 작용하는 클라이언트
│   │   ├── __init__.py
│   │   ├── github_service.py   # GitHub API와 상호 작용
│   │   └── llm_service.py      # AWS Bedrock (Langchain)과 상호 작용
│   │
│   └── slack/                  # Slack 관련 상호 작용 및 포맷팅
│       ├── __init__.py
│       ├── handler.py          # Slack 이벤트 콜백 및 명령어 처리
│       └── utils.py            # Slack Block Kit을 사용하여 메시지 포맷팅
│
└── slack_bot_gateway/          # 게이트웨이 람다용 소스 코드
    └── lambda_function.py      # Slack 확인 및 SQS 전달 처리
```

## 봇 확장하기

### 새 분석기 추가하기

1. **분석기 클래스 생성:**
   - `src/analyzers/` 디렉토리에 새 Python 파일(예: `my_analyzer.py`)을 만듭니다.
   - `analyzers.base_analyzer.BaseAnalyzer`를 상속하는 클래스(예: `MyAnalyzer`)를 정의합니다.
2. **추상 메소드 구현:**
   - `analyze(self, file_content: str, file_path: str) -> Dict[str, Any]`: 단일 파일 콘텐츠를 파싱하고 원시 결과를 반환하는 로직을 구현합니다.
   - `aggregate_results(self, analysis_outputs: List[Dict[str, Any]]) -> Dict[str, Any]`: 이 유형으로 분석된 여러 파일의 결과를 결합하는 로직을 구현합니다. 반환 딕셔너리에는 `results`, `recommendations`, `reasoning`과 같은 키가 포함되는 것이 이상적입니다.
   - `relevant_file_patterns(self) -> List[str]`: 이 분석기와 관련된 파일 경로와 일치하는 정규식 패턴 목록(예: `[r"\.myconfig$"]`)을 반환합니다.
   - `analysis_key(self) -> str`: 이 분석기의 집계된 결과가 최종 출력에서 저장될 고유 키(예: `"my_config_findings"`)를 반환합니다.
3. **분석기 등록:**
   - `src/analysis_orchestrator.py`를 엽니다.
   - 새 분석기 클래스를 가져옵니다.
   - `__init__` 메소드 내의 `_analyzer_instances` 딕셔너리에 매핑을 추가합니다 (예: `"my_analyzer": MyAnalyzer`).
4. **설정 추가:**
   - `src/config.py`를 엽니다.
   - `ENABLED_ANALYZERS`에 새 환경 변수 항목을 추가합니다 (예: `"my_analyzer": os.environ.get("ENABLE_MY_ANALYZER", "False").lower() == "true"`).
5. **LLM 프롬프트 업데이트 (선택 사항):**
   - LLM 요약을 사용하는 경우, `src/services/llm_service.py`의 `PROMPT_TEMPLATE_STR`을 수정하여 LLM이 새 `analysis_key`의 결과를 해석하고 표시하는 방법을 지시합니다.

### 새 의존성 검사기 추가하기

1. **검사기 클래스 생성:**
   - `src/analyzers/dependency_analyzer/`에 새 파일(예: `java_checker.py`)을 만듭니다.
   - `analyzers.dependency_analyzer.base_checker.BaseDependencyChecker`를 상속하는 클래스(예: `JavaDependencyChecker`)를 정의합니다.
2. **추상 메소드 구현:**
   - `parse_dependencies(self, file_content: str, file_path: str) -> List[Dict[str, Any]]`: 의존성 매니페스트 파일(예: `pom.xml`)을 파싱하고 의존성 딕셔너리 목록을 반환합니다.
   - `check_compatibility(self, dependency_info: Dict[str, Any]) -> Dict[str, Any]`: 파싱된 단일 의존성의 ARM 호환성을 확인합니다 (예: Maven Central 확인, 휴리스틱 사용). `compatible` (bool/str) 및 `reason` (str)을 포함한 딕셔너리를 반환합니다.
3. **검사기 등록:**
   - `src/analyzers/dependency_analyzer/manager.py`를 엽니다.
   - 새 검사기 클래스를 가져옵니다.
   - `__init__`의 `_checkers` 딕셔너리에 인스턴스를 추가합니다 (예: `"java": JavaDependencyChecker()`).
   - 관련 파일 경로를 인식하도록 `_get_checker_and_type`을 업데이트합니다 (예: `elif file_path.lower().endswith("pom.xml"): return self._checkers.get("java"), "java"`).
   - `DependencyManager`의 `relevant_file_patterns`에 새 매니페스트 파일 패턴(예: `r"pom\.xml$"`)을 추가합니다.
   - (선택 사항) 새 언어 유형에 대한 `aggregate_results`의 권장 사항/추론 생성을 조정합니다.

### Slack 메시지 수정하기

- `src/slack/utils.py` 내의 함수를 편집하여 Block Kit을 사용하여 Slack으로 전송되는 메시지의 구조나 내용을 변경합니다.

## 기여하기

기여를 환영합니다! 버그, 기능 요청 또는 개선 사항에 대한 풀 리퀘스트나 이슈를 자유롭게 제출해 주세요.

## 라이선스

이 프로젝트는 Apache 라이선스 2.0에 따라 라이선스가 부여됩니다 - 자세한 내용은 [LICENSE](LICENSE) 파일(존재하는 경우)을 참조하세요.

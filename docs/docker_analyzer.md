# DockerAnalyzer 모듈 README

## 👋 개요

`DockerAnalyzer`에 오신 것을 환영합니다! 이 파이썬 모듈은 AWS 인스턴스(또는 다른 클라우드 인스턴스)를 비용 절감 및 성능 향상을 위해 x86에서 ARM 아키텍처(예: AWS Graviton)로 마이그레이션하는 것을 추천하는 시스템의 핵심 부분입니다.

특히 이 분석기는 주어진 Git 리포지토리 내의 **Dockerfile**에 중점을 둡니다. 주요 목표는 Dockerfile이 현재 `amd64`(x86_64)용 빌드를 명시하더라도, 해당 Dockerized 애플리케이션이 ARM64 아키텍처에서 성공적으로 실행될 **잠재력**이 있는지를 평가하는 것입니다.

이 분석기는 Dockerfile을 분석하여 다음을 수행합니다:

1. 사용된 베이스 이미지를 식별합니다.
2. Docker Registry API를 쿼리하여 해당 베이스 이미지가 `linux/arm64` 아키텍처를 **네이티브하게 지원**하는지 확인합니다.
3. Dockerfile 내에서 하드코딩된 x86 의존성을 나타낼 수 있는 특정 명령어 또는 패턴(예: 특정 바이너리 다운로드, x86 아키텍처 명시적 추가)을 탐지합니다.
4. 이러한 결과를 종합하여 ARM 마이그레이션 잠재력("높음", "중간", "낮음")에 대한 전반적인 평가와 실행 가능한 권장 사항을 제공합니다.

## ✨ 주요 기능

- **Dockerfile 검색:** 일반적인 Dockerfile 이름 패턴(예: `Dockerfile`, `Dockerfile.dev`, `*.dockerfile`)과 일치하는 파일을 찾습니다.
- **여러 줄 명령어 처리:** `\` 문자를 사용하여 여러 줄에 걸쳐 작성된 Dockerfile 명령어를 올바르게 파싱합니다.
- **베이스 이미지 추출:** `FROM` 명령어를 식별하고, 베이스 이미지 이름과 명시적으로 사용된 `--platform` 플래그를 기록합니다.
- **아키텍처 명령어 탐지:** `RUN`, `COPY`, `ADD`, `ARG`, `ENV` 명령어 내에서 특정 아키텍처와 관련된 키워드 및 패턴(`amd64`, `x86_64`, `arm64`, `aarch64`, `--platform`, `TARGETARCH`, 특정 바이너리 다운로드, `dpkg`를 통한 아키텍처 추가 등)을 스캔합니다.
- **레지스트리 매니페스트 검사:**
  - Docker Registry API(현재 주로 Docker Hub)에 연결하여 지정된 베이스 이미지의 매니페스트를 확인합니다.
  - 이미지 매니페스트(또는 매니페스트 목록/OCI 인덱스)에 `linux/arm64` 변형이 공식적으로 포함되어 있는지 확인합니다.
  - 다중 아키텍처 매니페스트(목록)와 단일 아키텍처 매니페스트(신뢰성을 위해 config blob 검사)를 모두 처리합니다.
  - Docker Hub에 대한 기본 인증 지원을 포함합니다 (`config.py`의 자격 증명 사용 또는 익명 액세스).
  - 성능 향상 및 API 요청 제한(rate limit) 회피를 위해 매니페스트 검사 결과와 인증 토큰을 캐싱합니다.
- **잠재력 평가:** 분석된 모든 Dockerfile의 결과를 종합합니다.
- **실행 가능한 권장 사항:** 성공적인 ARM 마이그레이션을 위해 변경하거나 확인해야 할 사항에 대한 구체적인 조언을 제공합니다 (예: `--platform` 제거, 베이스 이미지 교체, 특정 명령어 확인).

## 🤔 작동 원리 (핵심 로직)

분석기는 상위 스크립트 또는 시스템에 의해 조정되는 두 가지 주요 단계로 작동합니다:

1. **파일별 분석 (`analyze` 메소드):**

   - 단일 Dockerfile의 내용과 경로를 입력으로 받습니다.
   - **전처리:** `\`로 이어진 라인을 병합하여 여러 줄 명령어를 단일 논리 단위로 처리합니다.
   - **베이스 이미지 추출:** 정규식을 사용하여 `FROM` 라인을 찾고, 베이스 이미지 이름과 사용된 `--platform` 플래그를 캡처합니다.
   - **아키텍처 관련 라인 탐지:** 정규식(키워드 및 특정 패턴)을 사용하여 관련 명령어(RUN, COPY 등) 내에서 아키텍처 의존성을 나타낼 수 있는 라인을 찾습니다.
   - **출력:** 해당 _단일_ 파일에 대해 추출된 `base_images_info`(딕셔너리 리스트)와 `arch_specific_lines`(문자열 리스트)를 포함하는 딕셔너리를 반환합니다.

2. **결과 집계 (`aggregate_results` 메소드):**
   - 딕셔너리 리스트(`analyze` 메소드가 발견된 모든 Dockerfile에 대해 반환한 결과들의 리스트)를 입력으로 받습니다.
   - **1단계: 데이터 수집:**
     - 모든 파일에서 고유한 베이스 이미지 이름(태그 포함, 기본값 'latest')을 모두 수집합니다.
     - 어떤 파일이 어떤 이미지를 사용하고 각 이미지에 어떤 `--platform` 플래그가 사용되었는지 추적합니다.
     - 모든 파일에서 발견된 고유한 아키텍처 관련 라인을 모두 수집하고 해당 라인이 발견된 소스 파일을 추적합니다.
   - **2단계: 매니페스트 확인 (핵심 단계):**
     - 식별된 각 고유 베이스 이미지에 대해:
       - `_check_image_compatibility_via_manifest(image_name)`를 호출합니다.
       - **`_check_...` 내부:**
         - 먼저 캐시(`_DOCKER_MANIFEST_CACHE`)를 확인합니다.
         - `_parse_image_name`을 사용하여 이미지 이름을 레지스트리, 리포지토리, 태그/다이제스트로 파싱합니다 (참고: 현재 파싱은 수동 방식, 제한 사항 참조). `scratch`를 특별 케이스로 처리합니다.
         - Docker Hub인 경우, `_get_docker_auth_token`을 사용하여 인증 토큰을 가져옵니다 (`config.py`의 자격 증명 또는 익명 처리, `사용자:리포지토리`별 토큰 캐싱).
         - 매니페스트 요청을 위한 Docker Registry API V2 URL을 구성합니다.
         - 적절한 `Accept` 헤더와 함께 HTTP 요청을 보냅니다.
         - `Content-Type`에 따라 응답을 파싱합니다 (`startswith` 사용으로 안정성 확보):
           - **매니페스트 목록 / OCI 인덱스:** 목록에 있는 매니페스트들을 순회하며 `platform.os == "linux"`이고 `platform.architecture`가 `["arm64", "aarch64"]` 중 하나인 항목을 찾습니다.
           - **단일 매니페스트:** 매니페스트에서 참조하는 구성 blob(config blob)을 가져옵니다 (아키텍처 정보에 더 신뢰성 높음). config JSON 내의 `os` 및 `architecture` 필드를 확인합니다. 필요한 경우 덜 신뢰성 있는 최상위 필드로 대체합니다.
         - 네이티브 ARM64 지원 여부(`compatible: True/False/unknown`)와 그 이유를 결정합니다.
         - 결과를 캐시에 저장합니다.
   - **3단계: 평가 및 권장 사항 생성:**
     - 집계된 이미지 데이터(매니페스트 결과 포함)를 순회합니다.
     - 각 이미지에 대한 상세 `assessment` 딕셔너리를 생성합니다 (네이티브 ARM 지원 상태, 사용된 플랫폼, 관련 파일 등 포함).
     - 주로 베이스 이미지의 네이티브 ARM 지원 여부에 기반하여 초기 `migration_potential`(마이그레이션 잠재력)을 결정합니다.
     - 1단계에서 수집된 `arch_specific_lines`를 검토합니다:
       - 잠재적인 "차단 요소"(예: `amd64.deb` 다운로드) 또는 "검토 필요" 항목(예: `.so` 파일 복사, 일반적인 `amd64` 키워드)을 식별합니다.
     - 베이스 이미지 호환성 및 특정 명령어에서 발견된 문제의 심각도에 따라 `overall_arm_potential`("높음", "중간", "낮음")을 조정합니다.
     - 사용자 친화적인 `reasoning`(근거) 문자열을 생성하여 결과를 설명합니다.
     - 실행 가능한 `recommendations`(권장 사항) 리스트를 만듭니다.
   - **출력:** `image_assessments`(리스트), `recommendations`(리스트), `reasoning`(리스트), `overall_potential`(문자열)을 포함하는 최종 딕셔너리를 반환합니다.

## 🧩 주요 구성 요소

- **`DockerAnalyzer(BaseAnalyzer)`:** 분석 로직을 구현하는 메인 클래스. 추상 `BaseAnalyzer`(다른 곳에 정의된 것으로 추정)를 상속하여 표준 인터페이스를 준수합니다.
- **`analyze(file_content, file_path)`:** 단일 Dockerfile을 분석합니다.
- **`aggregate_results(analysis_outputs)`:** 여러 `analyze` 호출 결과를 집계합니다.
- **`_check_image_compatibility_via_manifest(image_name_full)`:** Docker Registry API를 통해 핵심적인 호환성 검사를 수행합니다.
- **`_parse_image_name(image_name)`:** 이미지 이름을 분해하는 헬퍼 함수 (참고: 제한 사항 참조).
- **`_get_docker_auth_token(registry, repository)`:** Docker Hub 인증 토큰을 가져오는 헬퍼 함수 (참고: Docker Hub 특정).
- **캐시 (`_DOCKER_MANIFEST_CACHE`, `_DOCKER_AUTH_TOKEN_CACHE`):** 결과 및 토큰 캐싱을 위한 모듈 수준 딕셔너리.

## ⚙️ 입력 / 출력 / 설정

- **입력:**
  - `analyze`: `file_content` (문자열), `file_path` (문자열).
  - `aggregate_results`: 딕셔너리 리스트, 각 딕셔너리는 `analyze` 호출의 출력입니다.
- **출력 (`aggregate_results`):** 다음 키를 포함하는 딕셔너리:

  - `image_assessments`: (List[Dict]) 발견된 각 고유 베이스 이미지에 대한 상세 정보. 예시 항목:

        ```json
        {
          "image": "python:3.9-slim-buster",
          "files": ["Dockerfile", "dev.Dockerfile"],
          "platforms_explicitly_used": ["linux/amd64"],
          "arm64_support_native": true,
          "native_support_reason": "Image manifest supports linux/arm64.",
          "native_architectures": ["linux/amd64", "linux/arm64", "linux/arm/v7"],
          "migration_potential": "High",
          "required_actions": ["Remove or change `--platform=linux/amd64` flag in FROM lines."]
        }
        ```

  - `recommendations`: (List[str]) 사용자를 위한 실행 가능한 단계 목록. 전체 요약으로 시작합니다.
  - `reasoning`: (List[str]) 권장 사항의 근거가 되는 상세 설명.
  - `overall_potential`: (str) "High"(높음), "Medium"(중간), 또는 "Low"(낮음).

- **설정:**
  - 모듈에서 import 가능한 위치(예: 동일 디렉토리 또는 설정된 Python 경로)에 `config.py` 파일이 필요합니다.
  - `config.py`는 (선택적으로) 다음을 정의해야 합니다:
    - `DOCKERHUB_USERNAME` (문자열)
    - `DOCKERHUB_PASSWORD` (문자열)
  - 자격 증명이 제공되지 않거나 import에 실패하면 분석기는 익명 Docker Hub 액세스로 대체되며, 이 경우 더 엄격한 API 요청 제한이 적용될 수 있고 비공개 리포지토리에 접근할 수 없습니다.

## ⚠️ 제한 사항 & 향후 개선점

- **이미지 이름 파싱:** 현재 `_parse_image_name` 함수는 수동 문자열 처리 및 정규식을 사용합니다. 일반적인 경우는 처리하지만, OCI 배포 사양에 정의된 복잡한 엣지 케이스에서는 실패할 수 있습니다.
  - **TODO:** 수동 파싱을 `docker-image-py`와 같은 검증되고 강력한 라이브러리로 교체하는 것을 고려해야 합니다. 이는 코드 복잡성을 줄이고 정확성을 향상시킬 것입니다. (`_parse_image_name` 독스트링 참조).
- **레지스트리 지원:** 매니페스트 확인 및 인증은 현재 **Docker Hub**에 최적화되어 있습니다. 다른 레지스트리(ECR, GHCR, GCR 등)는 지원이 제한적이어서 "unknown" 호환성 상태를 반환할 가능성이 높습니다.
  - **TODO:** 다른 레지스트리 지원을 구현해야 합니다:
    - Bearer 토큰 인증을 위한 `Www-Authenticate` 헤더 파싱 (GHCR, GCR 등에 일반적).
    - ECR을 위한 AWS 특정 인증 구현 (예: `boto3` 사용 및 Lambda에 적절한 IAM 역할 부여 가정). (`_check_image_compatibility_via_manifest` 독스트링 참조).
- **정적 분석만 수행:** 이 분석기는 Dockerfile 텍스트와 이미지 매니페스트만 확인합니다. 다음은 수행할 수 없습니다:
  - `RUN` 명령어 내부에서 `git clone`으로 복제한 소스 코드가 실제로 ARM과 호환되는지 확인.
  - 명백한 아키텍처 이름 없이 복사된 바이너리가 x86인지 ARM인지 확인.
  - 모든 검사를 통과하더라도 애플리케이션 로직 자체가 ARM에서 올바르게 실행될 것이라고 보장. **테스트는 항상 필수입니다!**
- **Dockerfile 복잡성:** 고급 기능(명령어에 영향을 미치는 복잡한 `ARG`/`ENV` 로직 등)을 사용하는 매우 복잡한 Dockerfile은 완전히 해석되지 않을 수 있습니다.

## 🚀 사용 및 통합 방법

이 모듈은 더 큰 분석 파이프라인의 일부로 사용되도록 설계되었습니다:

1. 메인 스크립트가 리포지토리에서 관련 파일을 식별합니다 (`relevant_file_patterns` 사용).
2. 식별된 각 Dockerfile에 대해:
   - 파일 내용을 읽습니다.
   - `docker_analyzer.analyze(content, path)`를 호출합니다.
   - 결과 딕셔너리를 저장합니다.
3. 모든 Dockerfile 분석 후, 결과 딕셔너리 리스트를 `docker_analyzer.aggregate_results(list_of_analyze_outputs)`에 전달합니다.
4. 최종 집계된 딕셔너리(권장 사항, 근거 등 포함)를 사용하여 사용자 보고서를 생성합니다.

## 🛠️ 수정 및 기여 방법

- **파일 탐지 변경:** `relevant_file_patterns` 속성의 정규식 리스트를 수정합니다.
- **아키텍처 탐지 개선:**
  - `analyze`의 `arch_keywords`에 새 키워드를 추가합니다.
  - `analyze`의 `arch_patterns`에 더 구체적인 정규식 패턴을 추가합니다.
  - `aggregate_results`에서 `all_arch_specific_lines`를 확인하는 로직을 개선하여 차단 요소와 검토 항목을 더 잘 분류합니다.
- **베이스 이미지 확인 개선:** `_check_image_compatibility_via_manifest`를 수정합니다. 이 부분이 가장 복잡합니다. 변경 사항에는 새로운 매니페스트 유형 지원 또는 아키텍처 추출 방식 개선이 포함될 수 있습니다.
- **레지스트리 지원 추가:** 주로 `_check_image_compatibility_via_manifest`(API 호출용) 및 잠재적으로 `_get_docker_auth_token`(또는 새 인증 메소드 추가)을 수정하여 다른 인증 흐름(Bearer 토큰, AWS 자격 증명)을 처리합니다.
- **이미지 파서 교체:** `_parse_image_name`을 외부 라이브러리를 사용하도록 업데이트하고 `_check_image_compatibility_via_manifest`의 호출 코드를 조정합니다. 라이브러리를 배포 패키지/Lambda 레이어에 추가하는 것을 잊지 마세요.
- **권장 사항 로직 변경:** `aggregate_results` 내의 마지막 "3단계" 섹션을 수정합니다.

이 README가 `DockerAnalyzer`를 이해하고 작업하는 데 도움이 되기를 바랍니다!

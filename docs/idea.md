사용자가 쿼리에서 요청한 것은 GitHub 저장소 URL을 챗봇에 주면 수동 개입 없이 챗봇이 자동으로 저장소를 분석해서 ARM64 호환성을 판단할 수 있게 만드는 방법입니다. 이를 위해서는 챗봇이 저장소의 파일 목록을 가져오고, 개별 파일의 내용을 가져와 분석하는 기능을 구현해야 합니다. 다행히도 GitHub는 이를 가능하게 하는 API를 제공합니다. 아래에 그 방법을 단계별로 설명하겠습니다.

---

### 1. **GitHub API를 활용한 저장소 분석**

GitHub는 REST API를 제공하며, 이를 통해 저장소의 파일 목록과 내용을 프로그래밍 방식으로 가져올 수 있습니다. 챗봇이 저장소 URL(예: `https://github.com/owner/repo`)을 받으면, API를 사용해 자동으로 분석을 진행할 수 있습니다.

#### **주요 단계**

- **저장소 파일 트리 가져오기**: 저장소의 전체 파일 구조를 확인합니다.
- **특정 파일 내용 가져오기**: Terraform 파일(`.tf`)이나 소스 코드 파일의 내용을 가져옵니다.
- **내용 분석**: ARM64 호환성을 판단하기 위해 파일을 파싱하고 필요한 정보를 추출합니다.

---

### 2. **구체적인 구현 방법**

#### **(1) GitHub API 인증**

- **왜 필요할까?**: 공개 저장소는 인증 없이도 API를 사용할 수 있지만, 요청 제한(rate limit)이 낮습니다. 개인 액세스 토큰(Personal Access Token)을 사용하면 제한을 완화하고 비공개 저장소도 접근할 수 있습니다.
- **방법**: 챗봇에 토큰을 안전하게 저장하고, API 요청 시 HTTP 헤더에 `Authorization: token YOUR_TOKEN`을 추가합니다.

#### **(2) 저장소 파일 트리 가져오기**

- **API 엔드포인트**: `GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1`
- **작동 방식**:
  1. 저장소 URL에서 `owner`와 `repo`를 추출합니다 (예: `owner/repo`).
  2. 기본 브랜치(보통 `main`)의 최신 커밋을 가져옵니다:  
     `GET /repos/{owner}/{repo}/branches/main`
  3. 응답에서 커밋 SHA를 얻고 (`branch.commit.sha`), 커밋 정보를 가져옵니다:  
     `GET /repos/{owner}/{repo}/git/commits/{commit_sha}`
  4. 커밋 응답에서 트리 SHA를 얻습니다 (`commit.tree.sha`).
  5. 트리 SHA로 전체 파일 목록을 가져옵니다:  
     `GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1`
- **결과**: 파일 경로(`path`), 유형(`type`, 예: `blob`은 파일, `tree`는 디렉토리) 등이 포함된 리스트를 받습니다.

#### **(3) 개별 파일 내용 가져오기**

- **API 엔드포인트**: `GET /repos/{owner}/{repo}/contents/{path}`
- **작동 방식**:
  - 트리에서 `.tf` 확장자를 가진 Terraform 파일이나 소스 코드 파일(예: `.py`, `.java`, `.go`)을 필터링합니다.
  - 각 파일의 경로를 사용해 내용을 요청합니다.
  - 응답에서 `content` 필드는 base64로 인코딩된 파일 내용을 제공하니, 이를 디코딩해 사용합니다.

#### **(4) 파일 내용 분석**

- **Terraform 파일 분석**:
  - `.tf` 파일 내용을 가져오면, HCL(HashiCorp Configuration Language)을 파싱해 인스턴스 타입(예: `instance_type = "t3.large"`)을 추출합니다.
  - 간단히 문자열 검색(예: `"instance_type ="`)으로도 가능하지만, 정확도를 높이려면 HCL 파싱 라이브러리(예: Python의 `hcl2`)를 사용할 수 있습니다.
  - 추출한 인스턴스 타입이 ARM64 지원 타입(예: `t4g`, `m6g`)으로 대체될 수 있는지 확인합니다.
- **소스 코드 분석**:
  - 의존성 파일(예: Python의 `requirements.txt`, Java의 `pom.xml`)을 찾아 내용을 가져옵니다.
  - ARM64와 호환되지 않는 라이브러리(예: x86 전용 네이티브 확장)가 있는지 확인합니다.
  - Dockerfile이 있다면 `FROM` 명령어(예: `FROM amd64/python:3.8`)를 확인해 아키텍처 의존성을 체크합니다.

#### **(5) ARM64 호환성 판단**

- Terraform의 인스턴스 타입과 소스 코드 의존성을 종합해 ARM64로 마이그레이션 가능한지 판단합니다.
- 예: Terraform이 `t3.large`(x86 전용)를 사용하고, 소스 코드에 x86 전용 의존성이 없다면, ARM64 인스턴스(예: `t4g.large`)로 변경 가능 여부를 제안합니다.

#### **(6) 결과 제공**

- 챗봇이 사용자에게 호환성 여부와 권장 사항(예: "인스턴스 타입을 `t4g.large`로 변경하세요")을 자연어로 전달합니다.

---

### 3. **챗봇에서 이를 구현하는 방법**

챗봇이 언어 모델(LLM)을 기반으로 작동한다고 가정하면, 저장소 전체를 프롬프트에 넣는 건 비효율적입니다. 대신, LLM이 API 호출과 분석을 단계적으로 수행할 수 있게 **함수 도구(Function Tools)**를 제공해야 합니다.

#### **제안된 함수 도구**

- `get_repository_tree(owner, repo)`: 저장소의 전체 파일 트리를 반환.
- `get_file_content(owner, repo, path)`: 특정 파일의 내용을 반환.
- `analyze_terraform_file(content)`: Terraform 파일에서 인스턴스 타입을 추출.
- `check_source_code_compatibility(language, dependencies)`: 소스 코드의 ARM64 호환성을 확인.

#### **LLM 작동 방식**

1. 사용자가 `https://github.com/owner/repo`를 입력하면, LLM이 `get_repository_tree`를 호출해 파일 목록을 가져옵니다.
2. `.tf` 파일을 찾아 `get_file_content`로 내용을 가져오고, `analyze_terraform_file`로 분석합니다.
3. 의존성 파일을 찾아 `get_file_content`로 가져오고, `check_source_code_compatibility`로 호환성을 확인합니다.
4. 결과를 종합해 사용자에게 답변을 생성합니다.

#### **기술적 요구사항**

- 챗봇 프레임워크가 HTTP 요청(예: Python의 `requests`)과 함수 호출을 지원해야 합니다.
- GitHub API 토큰은 환경 변수 등으로 안전하게 관리합니다.

---

### 4. **최종 답변**

GitHub 저장소 URL을 챗봇에 주면 알아서 ARM64 호환성을 분석하게 하려면 다음 단계를 따르세요:

1. **GitHub API 사용**:
   - `GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1`로 파일 트리를 가져오고,
   - `GET /repos/{owner}/{repo}/contents/{path}`로 개별 파일 내용을 가져옵니다.
2. **파일 분석**:
   - Terraform 파일(`.tf`)에서 인스턴스 타입을 추출해 ARM64 지원 여부를 확인합니다.
   - 소스 코드 의존성 파일(예: `requirements.txt`)이나 Dockerfile을 분석해 아키텍처 의존성을 체크합니다.
3. **챗봇에 함수 도구 제공**:
   - `get_repository_tree`, `get_file_content`, `analyze_terraform_file`, `check_source_code_compatibility` 같은 함수를 정의해 LLM이 호출하게 합니다.
4. **자동화**: LLM이 함수를 단계적으로 실행해 저장소를 분석하고, 결과를 사용자에게 전달합니다.

이렇게 하면 챗봇이 저장소 URL만으로 자동으로 파일을 가져와 분석하고, ARM64 호환성을 판단할 수 있습니다. GitHub API 덕분에 이 모든 과정이 프로그래밍 방식으로 가능합니다!

# Repo ARM Checker

리포지토리의 ARM 아키텍처 호환성을 검사하는 도구입니다.

## 설치 방법

```bash
git clone https://github.com/username/repo_arm_checker.git
cd repo_arm_checker
pip install -r requirements.txt
```

## 사용 방법

### 기본 사용법

```bash
python arm_checker.py --repo [REPOSITORY_URL]
```

### 예시

```bash
# GitHub 리포지토리 검사
python arm_checker.py --repo https://github.com/username/project

# 로컬 리포지토리 검사
python arm_checker.py --repo ./local/repo/path
```

## 명령어 옵션

| 옵션          | 설명                                    |
| ------------- | --------------------------------------- |
| `--repo`      | 검사할 리포지토리의 URL 또는 경로       |
| `--output`    | 결과 출력 파일 (기본값: `results.json`) |
| `--verbose`   | 상세 정보 출력 모드 활성화              |
| `--skip-deps` | 종속성 검사 건너뛰기                    |

## 현재 지원 기능

현재 이 도구는 다음 항목만 분석합니다:

- Python requirements.txt 패키지 종속성

향후 버전에서는 다음 기능이 추가될 예정입니다:

- package.json (Node.js)
- pom.xml (Java)
- Dockerfile 이미지 분석
- Terraform 인스턴스 분석

## 결과 해석하기

검사 결과는 다음과 같은 형식으로 제공됩니다:

- ✅ ARM 호환: 리포지토리가 ARM 아키텍처와 완벽하게 호환됩니다.
- ⚠️ 부분 호환: 일부 코드나 종속성에 호환성 문제가 있을 수 있습니다.
- ❌ 비호환: 중요한 호환성 문제가 발견되었습니다.

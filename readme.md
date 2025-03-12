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

```

## 명령어 옵션

| 옵션        | 설명                                    |
| ----------- | --------------------------------------- |
| `--repo`    | 검사할 리포지토리의 URL 또는 경로       |
| `--output`  | 결과 출력 파일 (기본값: `results.json`) |
| `--verbose` | 상세 정보 출력 모드 활성화              |

## 현재 지원 기능

현재 이 도구는 다음 항목만 분석합니다:

- Python requirements.txt 패키지 종속성

향후 버전에서는 다음 기능이 추가될 예정입니다:

- package.json (Node.js), pom.xml (Java) 와 같이 다른 언어의 패키지 종속성 정의 파일 지원
- Dockerfile 이미지 분석
- Terraform 인스턴스 분석

## 결과 해석하기

검사 결과는 다음과 같은 형식으로 제공됩니다:

- **완전 호환(True)**: ARM 전용 wheel 또는 플랫폼 독립적인 universal wheel 존재 시
- **부분 호환(partial)**: 소스 배포판만 존재하며 C/Cython 확장 코드가 있어 컴파일 필요 시
- **비호환(False)**: ARM 지원 wheel이나 소스 배포판이 전혀 없을 시
- **판단 불가(unknown)**: PyPI API 오류 등 예외 발생 시

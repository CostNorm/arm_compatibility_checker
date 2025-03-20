# ARM64 호환성 분석 결과

## 저장소: CostNorm/arm_compatibility_checker

## 호환성: ✅ compatible

## 상세 분석

- 인스턴스 타입: 0 이슈
- 도커 이미지: 0 이슈
- 종속성: 8 분석됨 (5 직접, 3 전이적), 0 이슈

## LLM 평가

## ARM64 호환성 평가 결과

제공된 분석 결과에 따르면, 이 GitHub 저장소는 ARM64 아키텍처와 전반적으로 **호환**됩니다. 명시적으로 비호환되는 요소가 발견되지 않았기 때문입니다.

활성화된 분석기(`dependency`)에 대한 세부 분석 결과는 다음과 같습니다:

**`dependency` 분석기:**

소프트웨어 종속성 분석 결과, 모든 종속성이 ARM64 아키텍처와 호환되는 것으로 확인되었습니다.

*   **직접 종속성:** `requests`, `langchain`, `langchain-google-genai`, `python-dotenv`, `pipgrip`는 모두 범용 휠(universal wheel) 또는 ARM 특정 휠을 제공하여 ARM64 환경에서 문제없이 설치 및 실행될 수 있습니다.
*   **간접 종속성:** `typing-extensions`, `annotated-types`, `pydantic-core` 역시 범용 휠 또는 ARM 특정 휠을 제공하므로 호환됩니다. 특히, `pydantic-core`는 다양한 Python 버전 및 운영체제에 대한 ARM64용 휠을 제공하여 폭넓은 호환성을 보장합니다.

종속성과 관련하여, 별도의 마이그레이션 권장 사항은 없습니다. 모든 종속성이 ARM64를 지원합니다.


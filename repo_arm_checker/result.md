# ARM64 호환성 분석 결과

## 저장소: CostNorm/arm_compatibility_checker

## 호환성: ✅ compatible

## 상세 분석

- 인스턴스 타입: 0 이슈
- 도커 이미지: 0 이슈
- 종속성: 11 이슈

## LLM 평가

## ARM64 호환성 평가 결과

제공된 분석 결과에 따르면, 이 저장소는 ARM64 아키텍처와 **호환됩니다**.  분석 결과 명시적으로 비호환되는 요소가 발견되지 않았기 때문입니다.

활성화된 분석기(`dependency`)에 대한 세부 분석은 다음과 같습니다:

**`dependency` 분석기:**

소프트웨어 종속성 분석 결과, 모든 종속성이 ARM64 아키텍처와 호환됩니다.

*   **직접 종속성:**
    *   `requests==2.31.0`: 범용 휠(`requests-2.32.3-py3-none-any.whl`)이 제공되므로 호환됩니다.
    *   `langchain==0.0.267`: 범용 휠(`langchain-0.3.20-py3-none-any.whl`)이 제공되므로 호환됩니다.
    *   `langchain-google-genai==0.0.5`: 범용 휠(`langchain_google_genai-2.0.11-py3-none-any.whl`)이 제공되므로 호환됩니다.
    *   `python-dotenv==1.0.0`: 범용 휠(`python_dotenv-1.0.1-py3-none-any.whl`)이 제공되므로 호환됩니다.

*   **간접 종속성:**
    *   `anyio`, `jsonpatch`, `langsmith`, `packaging`, `pydantic`, `pyyaml`, `tenacity`: 모두 범용 휠 또는 ARM64 특정 휠이 제공되므로 호환됩니다. 특히 `pyyaml`은 다양한 ARM64 환경(예: `manylinux_2_17_aarch64`, `macosx_11_0_arm64`)을 위한 휠이 제공되어 폭넓은 호환성을 보장합니다.

종속성과 관련하여 추가적인 마이그레이션 권장 사항은 없습니다. 모든 종속성이 ARM64를 지원합니다.

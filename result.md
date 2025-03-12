# ARM64 호환성 분석 결과

## 저장소: CostNorm/arm_compatibility_checker

## 호환성: ✅ compatible

## 상세 분석

- 인스턴스 타입: 0 이슈
- 도커 이미지: 0 이슈
- 종속성: 8 분석됨 (5 직접, 3 전이적), 0 이슈

## LLM 평가

## ARM64 호환성 평가

제공된 분석 결과에 따르면, 이 GitHub 저장소는 ARM64 아키텍처와 전반적으로 호환됩니다. 명시적으로 비호환되는 요소가 발견되지 않았으며, 분석된 모든 종속성이 ARM64를 지원합니다.

**종속성 분석 (dependency):**

활성화된 `dependency` 분석기에 따라, `requirements.txt` 파일에 명시된 모든 소프트웨어 종속성은 ARM64 아키텍처와 호환됩니다.

*   **직접 종속성:**
    *   `requests==2.32.3`: 범용 휠 (`requests-2.32.3-py3-none-any.whl`)을 사용할 수 있으므로 호환됩니다.
    *   `langchain==0.3.20`: 범용 휠 (`langchain-0.3.20-py3-none-any.whl`)을 사용할 수 있으므로 호환됩니다.
    *   `langchain-google-genai==2.0.11`: 범용 휠 (`langchain_google_genai-2.0.11-py3-none-any.whl`)을 사용할 수 있으므로 호환됩니다.
    *   `python-dotenv==1.0.1`: 범용 휠 (`python_dotenv-1.0.1-py3-none-any.whl`)을 사용할 수 있으므로 호환됩니다.
    *   `pipgrip==0.10.14`: 범용 휠 (`pipgrip-0.10.14-py2.py3-none-any.whl`)을 사용할 수 있으므로 호환됩니다.

*   **간접 종속성:**
    *   `typing-extensions`: 범용 휠 (`typing_extensions-4.12.2-py3-none-any.whl`)을 사용할 수 있으므로 호환됩니다.
    *   `annotated-types`: 범용 휠 (`annotated_types-0.7.0-py3-none-any.whl`)을 사용할 수 있으므로 호환됩니다.
    *   `pydantic-core`: ARM 특정 휠 (`pydantic_core-2.31.1-cp{version}-cp{version}-manylinux_2_17_aarch64.manylinux2014_aarch64.whl` 등 다양한 버전 및 플랫폼용)을 사용할 수 있으므로 호환됩니다.

모든 종속성이 ARM64를 지원하는 휠을 제공하므로, 별도의 마이그레이션 권장 사항은 없습니다.  `pip install -r requirements.txt` 명령어를 ARM64 환경에서 실행하면 필요한 모든 패키지가 올바르게 설치될 것입니다.

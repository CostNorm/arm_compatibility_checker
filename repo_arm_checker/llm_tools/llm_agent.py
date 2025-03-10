from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate
from config import GOOGLE_API_KEY


def get_llm():
    """Initialize and return the Gemini model."""
    print("\n🤖 Initializing Gemini LLM model...\n")
    return GoogleGenerativeAI(
        model="gemini-2.0-pro-exp-02-05", google_api_key=GOOGLE_API_KEY, temperature=0
    )


def get_llm_assessment(compatibility_result):
    """
    Use LLM to generate a natural language assessment of the ARM64 compatibility
    results and recommendations.
    """
    print("\n📊 Starting ARM64 compatibility assessment...")
    print(f"\n📥 Input compatibility data summary:")
    print(f"{'='*80}")

    # 입력 데이터 요약 출력
    result_str = str(compatibility_result)
    print(f"{result_str[:500]}..." if len(result_str) > 500 else result_str)
    print(f"{'='*80}")

    llm = get_llm()

    # Create a prompt template with enhanced guidance for dependency analysis
    template = """
    You are an expert in cloud computing architecture and ARM64 compatibility assessment.
    Based on the following analysis of a GitHub repository, provide a clear assessment of
    its ARM64 compatibility, including specific recommendations for migration if applicable.
    
    Compatibility Analysis:
    {compatibility_result}
    
    Instructions:
    1. Start with an overall assessment of ARM64 compatibility based on the provided context and reasoning.
    2. Explain key findings from the instance types, Docker images, and dependencies analysis.
    3. For dependency analysis, highlight whether Python packages have ARM64 wheels available or source distributions that can be compiled.
    4. For Docker images, indicate if platform specification (--platform=linux/arm64) is needed or if the images explicitly support ARM64.
    5. Provide specific, actionable recommendations for migration to ARM64, prioritizing critical issues.
    6. Refer to the reasoning and context provided in the analysis to explain your conclusions.
    7. Keep your response concise, technical, and directly useful to engineers.
    
    Note: You are currently counting korean users, so please use the Korean language for your response.
    """

    prompt = PromptTemplate(input_variables=["compatibility_result"], template=template)
    print("\n📝 Created prompt template for LLM")

    # LLMChain 대신 파이프 연산자(|) 사용
    chain = prompt | llm

    # Run the chain
    try:
        print("\n🔄 Sending data to LLM and awaiting response...")
        result = chain.invoke({"compatibility_result": str(compatibility_result)})
        print("\n✅ Received response from LLM")
        print("\n📤 Assessment result received")

        # 결과 형식이 바뀌었을 수 있으므로 체크
        if isinstance(result, str):
            output = result
        else:
            output = result if result is not None else "Unable to generate assessment"

        return output
    except Exception as e:
        error_msg = f"Error generating assessment: {str(e)}"
        print(f"\n❌ {error_msg}")
        return error_msg

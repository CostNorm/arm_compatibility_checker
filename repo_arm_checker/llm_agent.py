from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from config import GOOGLE_API_KEY


def get_llm():
    """Initialize and return the Gemini model."""
    return GoogleGenerativeAI(
        model="gemini-2.0-pro-exp-02-05", google_api_key=GOOGLE_API_KEY, temperature=0
    )


def get_llm_assessment(compatibility_result):
    """
    Use LLM to generate a natural language assessment of the ARM64 compatibility
    results and recommendations.
    """
    llm = get_llm()

    # Create a prompt template
    template = """
    You are an expert in cloud computing architecture and ARM64 compatibility assessment.
    Based on the following analysis of a GitHub repository, provide a clear assessment of
    its ARM64 compatibility, including specific recommendations for migration if applicable.
    
    Compatibility Analysis:
    {compatibility_result}
    
    Instructions:
    1. Start with an overall assessment of ARM64 compatibility.
    2. Explain key findings from the instance types, Docker images, and dependencies.
    3. Provide specific, actionable recommendations for migration to ARM64.
    4. Keep your response concise, technical, and directly useful to engineers.
    """

    prompt = PromptTemplate(input_variables=["compatibility_result"], template=template)

    # Create the chain
    chain = LLMChain(llm=llm, prompt=prompt)

    # Run the chain
    try:
        result = chain.invoke({"compatibility_result": str(compatibility_result)})
        return result.get("text", "Unable to generate assessment")
    except Exception as e:
        return f"Error generating assessment: {str(e)}"

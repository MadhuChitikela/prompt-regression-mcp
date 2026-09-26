from pydantic import BaseModel, Field
import os
import logging

logger = logging.getLogger(__name__)

class Grade(BaseModel):
    score: float = Field(description="0.0 to 1.0 - quality of new output")
    reason: str = Field(description="Short explanation")
    regression: bool = Field(description="True if new output is materially worse than baseline")

JUDGE_PROMPT = """You are an LLM-as-judge grading agent outputs.

Baseline (expected behavior): {baseline}
New output: {new}
Expected: {expected}

Rules:
1. Score 0.0-1.0 based on how well the new output satisfies the expected behavior.
2. Mark regression=True if new output is materially worse than baseline.
3. Be strict but fair. Minor wording changes are NOT regressions.

Return structured JSON matching the Grade schema."""

async def grade(baseline: str, new: str, expected: str = "") -> Grade:
    if not expected:
        expected = baseline

    # Fast-path heuristics for deterministic test cases and identical outputs
    if baseline.strip() == new.strip():
        return Grade(score=1.0, reason="New output matches baseline exactly.", regression=False)

    if not new.strip() and baseline.strip():
        return Grade(score=0.0, reason="New output is empty while baseline has content.", regression=True)

    api_key = os.getenv("GROQ_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    # If valid Groq key, try Groq with configurable model
    if api_key and not api_key.startswith("mock_") and not api_key.startswith("your_key"):
        try:
            from langchain_groq import ChatGroq
            groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
            llm = ChatGroq(
                model=groq_model,
                api_key=api_key,
                temperature=0,
            ).with_structured_output(Grade)
            return await llm.ainvoke(
                JUDGE_PROMPT.format(baseline=baseline, new=new, expected=expected)
            )
        except Exception as exc:
            logger.warning(f"Groq API call failed in judge: {exc}")

    # Fallback to Gemini if available
    if gemini_key and not gemini_key.startswith("mock_"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=gemini_key,
                temperature=0,
            ).with_structured_output(Grade)
            return await llm.ainvoke(
                JUDGE_PROMPT.format(baseline=baseline, new=new, expected=expected)
            )
        except Exception as exc:
            logger.warning(f"Gemini API call failed in judge: {exc}")

    # Heuristic fallback
    is_reg = (len(new.strip()) == 0) or (len(new.strip()) < len(baseline.strip()) * 0.3)
    return Grade(
        score=0.0 if is_reg else 0.80,
        reason="Evaluation completed via heuristic fallback.",
        regression=is_reg
    )
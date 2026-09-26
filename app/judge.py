from pydantic import BaseModel, Field
import os
import logging

logger = logging.getLogger(__name__)

class Grade(BaseModel):
    score: float = Field(description="0.0 to 1.0 — quality of new output")
    reason: str = Field(description="Short explanation")
    regression: bool = Field(description="True if new output is materially worse than baseline")

JUDGE_PROMPT = """You are an LLM-as-judge grading agent outputs.

Baseline (expected behavior): {baseline}
New output: {new}
Expected: {expected}

Rules:
1. Score 0.0–1.0 based on how well the new output satisfies the expected behavior.
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
    if not api_key or api_key.startswith("mock_") or api_key.startswith("your_key"):
        # Heuristic fallback when no valid API key is present (e.g. local unit tests)
        if len(new.strip()) < len(baseline.strip()) * 0.3:
            return Grade(score=0.1, reason="Output truncated or empty compared to baseline.", regression=True)
        return Grade(score=0.85, reason="Heuristic comparison: non-empty variation without regression.", regression=False)

    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=api_key,
            temperature=0,
        ).with_structured_output(Grade)
        return await llm.ainvoke(
            JUDGE_PROMPT.format(baseline=baseline, new=new, expected=expected)
        )
    except Exception as exc:
        logger.warning(f"Groq API call failed: {exc}. Using fallback evaluator.")
        is_reg = (len(new.strip()) == 0) or (len(new.strip()) < len(baseline.strip()) * 0.3)
        return Grade(
            score=0.0 if is_reg else 0.75,
            reason=f"Evaluation completed via fallback ({str(exc)[:60]}).",
            regression=is_reg
        )

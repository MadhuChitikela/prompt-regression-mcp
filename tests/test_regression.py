import pytest
from app.judge import grade

@pytest.mark.asyncio
async def test_judge_identical():
    g = await grade("The answer is 42", "The answer is 42", "The answer is 42")
    assert g.score > 0.9
    assert not g.regression

@pytest.mark.asyncio
async def test_judge_regression():
    g = await grade("The answer is 42", "", "The answer is 42")
    assert g.regression
    assert g.score < 0.5

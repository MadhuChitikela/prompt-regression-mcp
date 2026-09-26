import pytest
from app.mcp_server import (
    record_trace,
    query_traces,
    get_trace,
    diff_traces,
    promote_to_eval,
    replay_trace,
    grade_regression,
)
from app.agent_registry import register_agent
from tests.fake_agent import echo_agent

def test_record_and_query():
    r = record_trace("test-agent", "hello", "hi there", [], 100, 0.0, "abc")
    assert r["status"] == "recorded"
    traces = query_traces("test-agent", limit=5)
    assert len(traces) >= 1
    assert get_trace(r["trace_id"])["output"] == "hi there"

def test_missing_trace():
    assert "error" in get_trace("nonexistent")

def test_diff_traces():
    t1 = record_trace("diff-agent", "hello", "hi there", [], 100, 0.0, "abc")
    t2 = record_trace("diff-agent", "hello", "hello world", [], 120, 0.0, "def")
    diff = diff_traces(t1["trace_id"], t2["trace_id"])
    assert diff["input_same"] is True
    assert diff["output_changed"] is True
    assert diff["latency_delta_ms"] == 20

@pytest.mark.asyncio
async def test_replay_trace():
    register_agent("replay-agent", echo_agent)
    t = record_trace("replay-agent", "ping", "pong", [], 50, 0.0, "ghi")
    rep = await replay_trace(t["trace_id"])
    assert rep["original_id"] == t["trace_id"]
    assert rep["new_output"] == "Echo: ping"

@pytest.mark.asyncio
async def test_promote_and_grade():
    register_agent("grade-agent", echo_agent)
    t = record_trace("grade-agent", "my test input", "Echo: my test input", [], 50, 0.0, "v1")
    promo = promote_to_eval(t["trace_id"], expected="Echo: my test input")
    assert promo["status"] == "promoted"
    res = await grade_regression("grade-agent", commit_sha="v2")
    assert res["total"] >= 1
    assert res["regressions"] == 0

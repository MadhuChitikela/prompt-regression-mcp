import pytest
from app.tracer import Tracer
from app.mcp_server import query_traces

@pytest.mark.asyncio
async def test_tracer_async():
    tracer = Tracer(agent_id="tracer-test-agent")

    @tracer.trace
    async def sample_agent(user_input: str):
        return {"output": f"Processed: {user_input}", "tool_calls": [{"name": "calculator"}]}

    res = await sample_agent("calculate 2+2")
    assert res["output"] == "Processed: calculate 2+2"

    traces = query_traces("tracer-test-agent", limit=1)
    assert len(traces) == 1
    assert traces[0]["input"] == "calculate 2+2"
    assert "calculator" in str(traces[0]["tool_calls"])

def test_tracer_sync():
    tracer = Tracer(agent_id="tracer-sync-agent")

    @tracer.trace
    def sample_sync_agent(user_input: str):
        return {"output": f"Sync: {user_input}"}

    res = sample_sync_agent("sync input")
    assert res["output"] == "Sync: sync input"

    traces = query_traces("tracer-sync-agent", limit=1)
    assert len(traces) == 1
    assert traces[0]["output"] == "Sync: sync input"

from app.db import get_db
from app.tracer import git_sha
from datetime import datetime, timezone
import uuid
import json
import inspect
from typing import Callable, Any, Dict

async def replay(trace_id: str, agent_fn: Callable) -> Dict[str, Any]:
    """Re-executes the input of a previous trace through an agent function and records a new trace."""
    with get_db() as conn:
        original = conn.execute("SELECT * FROM traces WHERE id = ?", (trace_id,)).fetchone()
    if not original:
        return {"error": "trace not found"}

    start = datetime.now(timezone.utc)
    if inspect.iscoroutinefunction(agent_fn):
        result = await agent_fn(original["input"])
    else:
        result = agent_fn(original["input"])
    latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    output = result.get("output", str(result)) if isinstance(result, dict) else str(result)
    tool_calls = result.get("tool_calls", []) if isinstance(result, dict) else []
    cost_usd = result.get("cost_usd", 0.0) if isinstance(result, dict) else 0.0
    commit_sha = (result.get("git_sha", "") if isinstance(result, dict) else "") or git_sha()

    new_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_id,
                original["agent_id"],
                original["input"],
                output,
                json.dumps(tool_calls),
                latency,
                float(cost_usd),
                commit_sha,
                datetime.now(timezone.utc).isoformat()
            )
        )
    return {
        "original_id": trace_id,
        "replay_id": new_id,
        "original_output": original["output"],
        "new_output": output
    }

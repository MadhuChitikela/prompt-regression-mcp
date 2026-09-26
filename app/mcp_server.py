from fastmcp import FastMCP
from pydantic import Field
from typing_extensions import Annotated
from app.db import get_db, init_db
from app.replayer import replay
from app.agent_registry import get_agent
from app.judge import grade
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import uuid
import json

init_db()
mcp = FastMCP(name="prompt-regression")

@mcp.tool()
def record_trace(
    agent_id: Annotated[str, Field(description="Identifier for the agent, e.g. 'lead-qualifier'")],
    input: Annotated[str, Field(description="User input that triggered the run")],
    output: Annotated[str, Field(description="Final agent output")],
    tool_calls: Annotated[List[Dict[str, Any]], Field(description="List of tool calls made")] = None,
    latency_ms: Annotated[int, Field(description="Total latency in ms")] = 0,
    cost_usd: Annotated[float, Field(description="Estimated cost in USD")] = 0.0,
    git_sha: Annotated[str, Field(description="Git commit SHA")] = "",
) -> dict:
    """Persist a single agent run as a trace."""
    if tool_calls is None:
        tool_calls = []
    trace_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                agent_id,
                input,
                output,
                json.dumps(tool_calls),
                latency_ms,
                cost_usd,
                git_sha,
                datetime.now(timezone.utc).isoformat()
            )
        )
    return {"trace_id": trace_id, "status": "recorded"}

@mcp.tool()
def query_traces(
    agent_id: Annotated[str, Field(description="Agent identifier")],
    limit: Annotated[int, Field(description="Max traces to return")] = 20,
    since: Annotated[str, Field(description="ISO timestamp filter")] = "",
) -> list[dict]:
    """Search historical traces for an agent."""
    q = "SELECT * FROM traces WHERE agent_id = ?"
    params: list[Any] = [agent_id]
    if since:
        q += " AND created_at >= ?"
        params.append(since)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(q, params).fetchall()

    results = []
    for r in rows:
        item = dict(r)
        if isinstance(item.get("tool_calls"), str):
            try:
                item["tool_calls"] = json.loads(item["tool_calls"])
            except Exception:
                pass
        results.append(item)
    return results

@mcp.tool()
def get_trace(trace_id: Annotated[str, Field(description="Trace ID to fetch")]) -> dict:
    """Fetch a single trace by ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (trace_id,)).fetchone()
    if not row:
        return {"error": "not found"}
    item = dict(row)
    if isinstance(item.get("tool_calls"), str):
        try:
            item["tool_calls"] = json.loads(item["tool_calls"])
        except Exception:
            pass
    return item

@mcp.tool()
async def replay_trace(trace_id: Annotated[str, Field(description="Trace ID to replay")]) -> dict:
    """Re-run the original input against the current agent version."""
    trace = get_trace(trace_id)
    if "error" in trace:
        return trace
    try:
        agent_fn = get_agent(trace["agent_id"])
    except KeyError:
        return {"error": f"Agent '{trace['agent_id']}' is not registered in runtime"}
    return await replay(trace_id, agent_fn)

@mcp.tool()
def diff_traces(
    trace_a: Annotated[str, Field(description="Original or baseline trace ID")],
    trace_b: Annotated[str, Field(description="Comparison or replayed trace ID")],
) -> dict:
    """Show what changed between two trace runs."""
    a = get_trace(trace_a)
    b = get_trace(trace_b)
    if "error" in a or "error" in b:
        return {"error": "one or both traces missing"}
    return {
        "input_same": a["input"] == b["input"],
        "output_changed": a["output"] != b["output"],
        "latency_delta_ms": b["latency_ms"] - a["latency_ms"],
        "old_output": a["output"],
        "new_output": b["output"],
    }

@mcp.tool()
def promote_to_eval(
    trace_id: Annotated[str, Field(description="Trace ID to promote to eval suite")],
    expected: Annotated[str, Field(description="Expected output (defaults to original trace output)")] = "",
) -> dict:
    """Add a trace to the eval suite (usually a known failure or critical baseline)."""
    trace = get_trace(trace_id)
    if "error" in trace:
        return trace
    with get_db() as conn:
        conn.execute(
            "INSERT INTO evals (agent_id, trace_id, expected, added_at) VALUES (?, ?, ?, ?)",
            (
                trace["agent_id"],
                trace_id,
                expected or trace["output"],
                datetime.now(timezone.utc).isoformat()
            )
        )
    return {"status": "promoted", "trace_id": trace_id}

@mcp.tool()
async def grade_regression(
    agent_id: Annotated[str, Field(description="Agent identifier to evaluate")],
    commit_sha: Annotated[str, Field(description="Current commit SHA")] = "",
) -> dict:
    """Compare current agent version vs. baseline on all promoted evals."""
    with get_db() as conn:
        evals = conn.execute(
            "SELECT * FROM evals WHERE agent_id = ?", (agent_id,)
        ).fetchall()

    try:
        agent_fn = get_agent(agent_id)
    except KeyError:
        return {"error": f"Agent '{agent_id}' not registered", "regressions": 0, "total": 0, "results": []}

    results = []
    regressions = 0
    for e in evals:
        baseline = e["expected"]
        orig_trace = get_trace(e["trace_id"])
        if "error" in orig_trace:
            continue
        new = await agent_fn(orig_trace["input"])
        new_output = new.get("output", str(new)) if isinstance(new, dict) else str(new)
        g = await grade(baseline, new_output, expected=baseline)
        if g.regression:
            regressions += 1
        results.append({
            "trace_id": e["trace_id"],
            "score": g.score,
            "reason": g.reason,
            "regression": g.regression,
        })
        with get_db() as conn:
            conn.execute(
                "INSERT INTO grades (agent_id, trace_id, commit_sha, score, reason, regression, graded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    agent_id,
                    e["trace_id"],
                    commit_sha,
                    g.score,
                    g.reason,
                    1 if g.regression else 0,
                    datetime.now(timezone.utc).isoformat()
                )
            )
    return {
        "agent_id": agent_id,
        "total": len(evals),
        "regressions": regressions,
        "results": results
    }

@mcp.tool()
async def report_pr_comment(
    pr_id: Annotated[str, Field(description="PR number")],
    results: Annotated[dict, Field(description="Results dictionary from grade_regression")],
) -> dict:
    """Post regression summary to a GitHub PR. Writes to file for CI to post."""
    lines = [f"## Prompt Regression Report — PR #{pr_id}", ""]
    lines.append(f"**Agent:** `{results.get('agent_id', 'unknown')}`")
    lines.append(f"**Total evals:** {results.get('total', 0)}")
    lines.append(f"**Regressions:** {results.get('regressions', 0)}")
    lines.append("")
    for r in results.get("results", []):
        icon = "❌" if r.get("regression") else "✅"
        lines.append(f"- {icon} `{r['trace_id'][:8]}` — score {r.get('score', 0.0):.2f} — {r.get('reason', '')}")
    lines.append("")
    verdict = "**BLOCK MERGE**" if results.get("regressions", 0) > 0 else "**PASS**"
    lines.append(f"Verdict: {verdict}")
    body = "\n".join(lines)
    with open("pr_comment.md", "w", encoding="utf-8") as f:
        f.write(body)
    return {"status": "written", "path": "pr_comment.md", "body": body}

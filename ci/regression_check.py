import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure root directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_db
from app.mcp_server import grade_regression, report_pr_comment, record_trace, promote_to_eval
from app.agent_registry import register_agent
from tests.fake_agent import echo_agent

AGENT_ID = os.getenv("AGENT_ID", "echo-agent")
PR_ID = os.getenv("PR_ID", "0")
COMMIT_SHA = os.getenv("GITHUB_SHA", "")

register_agent(AGENT_ID, echo_agent)

def ensure_baseline_evals(agent_id: str) -> None:
    """Ensure baseline eval cases exist in the database for the agent."""
    with get_db() as conn:
        count = conn.execute("SELECT count(*) FROM evals WHERE agent_id = ?", (agent_id,)).fetchone()[0]
    if count == 0:
        test_cases = [
            ("Hello, check agent status", "Echo: Hello, check agent status"),
            ("Qualify lead: Acme Corp with $50k budget", "Echo: Qualify lead: Acme Corp with $50k budget"),
            ("Summarize customer issue: login failure", "Echo: Summarize customer issue: login failure"),
        ]
        for inp, expected in test_cases:
            rec = record_trace(
                agent_id=agent_id,
                input=inp,
                output=expected,
                latency_ms=100,
                cost_usd=0.0001,
                git_sha="baseline"
            )
            promote_to_eval(trace_id=rec["trace_id"], expected=expected)

async def main():
    ensure_baseline_evals(AGENT_ID)
    results = await grade_regression(AGENT_ID, COMMIT_SHA)
    with open("regression_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    await report_pr_comment(PR_ID, results)
    if results.get("regressions", 0) > 0:
        print(f"FAILED: Found {results['regressions']} regression(s).")
        sys.exit(1)
    print("SUCCESS: No regressions found.")

if __name__ == "__main__":
    asyncio.run(main())

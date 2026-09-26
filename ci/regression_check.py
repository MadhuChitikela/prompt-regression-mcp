import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure root directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.mcp_server import grade_regression, report_pr_comment
from app.agent_registry import register_agent
from tests.fake_agent import echo_agent

AGENT_ID = os.getenv("AGENT_ID", "echo-agent")
PR_ID = os.getenv("PR_ID", "0")
COMMIT_SHA = os.getenv("GITHUB_SHA", "")

register_agent(AGENT_ID, echo_agent)

async def main():
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

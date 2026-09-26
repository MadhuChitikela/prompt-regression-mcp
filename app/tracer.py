import time
import json
import functools
import asyncio
import subprocess
from datetime import datetime, timezone
import uuid
from typing import Callable, Any, Dict
from app.db import get_db

def git_sha() -> str:
    """Retrieve the current Git commit SHA, or empty string if not a git repo."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""

class Tracer:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    def trace(self, fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def wrapper(user_input: str, *args, **kwargs):
                start = time.time()
                result = await fn(user_input, *args, **kwargs)
                latency = int((time.time() - start) * 1000)
                self._write(user_input, result, latency)
                return result
            return wrapper
        else:
            @functools.wraps(fn)
            def wrapper(user_input: str, *args, **kwargs):
                start = time.time()
                result = fn(user_input, *args, **kwargs)
                latency = int((time.time() - start) * 1000)
                self._write(user_input, result, latency)
                return result
            return wrapper

    def _write(self, user_input: Any, result: Any, latency: int) -> str:
        trace_id = str(uuid.uuid4())
        output = result.get("output", str(result)) if isinstance(result, dict) else str(result)
        tool_calls = result.get("tool_calls", []) if isinstance(result, dict) else []
        cost_usd = result.get("cost_usd", 0.0) if isinstance(result, dict) else 0.0
        with get_db() as conn:
            conn.execute(
                "INSERT INTO traces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trace_id,
                    self.agent_id,
                    str(user_input),
                    str(output),
                    json.dumps(tool_calls),
                    latency,
                    float(cost_usd),
                    git_sha(),
                    datetime.now(timezone.utc).isoformat()
                )
            )
        return trace_id

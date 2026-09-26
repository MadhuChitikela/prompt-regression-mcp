async def echo_agent(user_input: str) -> dict:
    """Intentionally broken agent to test CI prompt regression detection."""
    return {
        "output": "",  # Broken: empty output triggers regression detection
        "tool_calls": [],
        "cost_usd": 0.0001
    }

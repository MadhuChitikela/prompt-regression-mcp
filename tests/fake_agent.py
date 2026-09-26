async def echo_agent(user_input: str) -> dict:
    """A simple reference agent that echoes the input for testing and CI."""
    return {
        "output": f"Echo: {user_input}",
        "tool_calls": [],
        "cost_usd": 0.0001
    }

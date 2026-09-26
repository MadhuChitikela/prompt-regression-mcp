from typing import Callable, Any, Dict

_registry: Dict[str, Callable] = {}

def register_agent(agent_id: str, fn: Callable) -> None:
    """Register an agent function by its unique identifier."""
    _registry[agent_id] = fn

def get_agent(agent_id: str) -> Callable:
    """Retrieve a registered agent function by ID."""
    if agent_id not in _registry:
        raise KeyError(f"Agent '{agent_id}' not registered")
    return _registry[agent_id]

def list_registered_agents() -> list[str]:
    """List all registered agent IDs."""
    return list(_registry.keys())

def clear_registry() -> None:
    """Clear registered agents (primarily for testing)."""
    _registry.clear()

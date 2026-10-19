"""
Backward compatibility layer for agent assistant.
The ReAct Single-Agent runner has been modularized into app.agent.graph and app.agent.tools.
"""
from app.agent.graph import execute_react_agent, execute_chat
from app.agent.tools import ALL_TOOLS, TOOLS_REGISTRY

__all__ = [
    "execute_react_agent",
    "execute_chat",
    "ALL_TOOLS",
    "TOOLS_REGISTRY"
]

"""The shop's MCP tools, shared by every agent.

One `MCPToolset` is built here and handed to all five agents, so the team runs
against a single server process rather than five. No agent touches the database
directly — the tools are the only route in, which is what makes the house rules
enforceable rather than merely stated.
"""

from __future__ import annotations

import sys

from pydantic_ai.mcp import MCPToolset, StdioTransport

from .settings import PROJECT_ROOT

#: The same server `.mcp.json` registers, launched with the interpreter that is
#: already running the backend. `sys.executable` is used rather than the literal
#: `./.venv/bin/python` from that file because it does not depend on the working
#: directory the backend happens to start in.
_transport = StdioTransport(
    command=sys.executable,
    args=["-m", "mcp_server.server"],
    cwd=str(PROJECT_ROOT),
)

shop_tools = MCPToolset(_transport, id="campus-customs")

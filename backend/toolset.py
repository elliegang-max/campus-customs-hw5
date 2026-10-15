"""The shop's MCP tools, shared by every agent.

One `MCPToolset` is built here and handed to all five agents, so the team runs
against a single server process rather than five. No agent touches the database
directly, and there is no second path to it — the tools are the only way in,
which is what makes the house rules enforceable rather than merely stated.

Two things happen on the way through:

* **Every tool call is audited.** `process_tool_call` records which agent called
  what, with which arguments, how long it took, and whether it raised.
* **`approve_payment` is hidden from the agents.** The server offers it so that
  a human approving a payment goes through the same audited path, but the
  agents' view of the toolset filters it out. An agent cannot approve its own
  proposal because it cannot see the tool at all.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from pydantic_ai.mcp import CallToolFunc, MCPToolset, StdioTransport, ToolResult
from pydantic_ai.tools import RunContext

from . import audit
from .settings import PROJECT_ROOT

#: Only a human may record an approval, so the agents never see this tool.
HUMAN_ONLY_TOOLS = {"approve_payment"}


async def _audited(
    ctx: RunContext[Any],
    call_tool: CallToolFunc,
    name: str,
    args: dict[str, Any],
) -> ToolResult:
    """Record every MCP tool call, including the ones that fail."""
    agent = getattr(ctx.agent, "name", None) or "unknown"
    started = time.perf_counter()
    try:
        result = await call_tool(name, args)
    except Exception as exc:
        audit.append(
            "tool_call",
            agent=agent,
            tool=name,
            arguments=args,
            step=ctx.run_step,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            ms=round((time.perf_counter() - started) * 1000),
        )
        raise
    audit.append(
        "tool_call",
        agent=agent,
        tool=name,
        arguments=args,
        step=ctx.run_step,
        ok=True,
        result=audit.summarise(result),
        ms=round((time.perf_counter() - started) * 1000),
    )
    return result


#: The same server `.mcp.json` registers, launched with the interpreter that is
#: already running the backend. `sys.executable` is used rather than the literal
#: `./.venv/bin/python` from that file because it does not depend on the working
#: directory the backend happens to start in.
_transport = StdioTransport(
    command=sys.executable,
    args=["-m", "mcp_server.server"],
    cwd=str(PROJECT_ROOT),
)

shop_tools = MCPToolset(
    _transport, id="campus-customs", process_tool_call=_audited
)

#: What the agents actually get.
agent_tools = shop_tools.filtered(lambda ctx, tool: tool.name not in HUMAN_ONLY_TOOLS)

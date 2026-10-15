"""Shared construction for every agent on the team.

Each agent is the same four things: the one allowed model, the shop's MCP
tools, a prompt file, and a typed output. Building them through one function
keeps those four consistent and means a rule added to `prompts/_shared.md`
reaches every agent at once.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, TypeVar

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.usage import UsageLimits

from . import audit
from .settings import PROMPTS_DIR, model
from .toolset import agent_tools

OutputT = TypeVar("OutputT")

#: The gateway refuses function tools on /v1/chat/completions unless reasoning
#: effort is off: "Function tools with reasoning_effort are not supported for
#: gpt-6-luna-global". Every agent on this team uses tools, so the setting is
#: applied once here rather than remembered at five call sites.
MODEL_SETTINGS = OpenAIChatModelSettings(openai_reasoning_effort="none")

#: Bounds one team run. Each tool round trip is a request, and the team shares
#: one budget: a three-ticket board through ten agent runs measured ~50
#: requests once the write tools were added. The cap has to cover the *whole*
#: run, not one agent's share of it — and it must be passed to the delegated
#: runs too, since an agent's own default (50) would otherwise fire first and
#: kill the run mid-way through a delegation.
MAX_REQUESTS_PER_RUN = 150


@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    """Read an agent prompt, with the shared house rules spliced in.

    The rules live in one file so they cannot drift between agents. A prompt
    marks where they go with `{SHARED_RULES}`.
    """
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    shared = (PROMPTS_DIR / "_shared.md").read_text(encoding="utf-8")
    if "{SHARED_RULES}" not in text:
        raise ValueError(f"prompt {name}.md must contain {{SHARED_RULES}}")
    return text.replace("{SHARED_RULES}", shared)


def build_agent(
    prompt_name: str,
    output_type: Any,
    *,
    name: str | None = None,
) -> Agent[None, Any]:
    """An agent with the one allowed model, the shop's tools, and a typed output."""
    return Agent(
        model(),
        name=name or prompt_name,
        instructions=load_prompt(prompt_name),
        model_settings=MODEL_SETTINGS,
        toolsets=[agent_tools],
        output_type=output_type,
    )


async def run_agent(
    agent: Agent[None, Any],
    prompt: str,
    *,
    usage: Any = None,
    delegated_by: str | None = None,
) -> Any:
    """Run an agent and record both ends of it in the audit trail.

    Every agent run goes through here — the Boss's own and each delegated one —
    so the trail shows the delegation tree, what each agent was asked, and what
    it came back with.
    """
    audit.append(
        "agent_started",
        agent=agent.name,
        delegated_by=delegated_by,
        prompt=audit.summarise(prompt),
    )
    started = time.perf_counter()
    try:
        limits = UsageLimits(request_limit=MAX_REQUESTS_PER_RUN)
        result = (
            await agent.run(prompt, usage=usage, usage_limits=limits)
            if usage is not None
            else await agent.run(prompt, usage_limits=limits)
        )
    except Exception as exc:
        audit.append(
            "agent_finished",
            agent=agent.name,
            delegated_by=delegated_by,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            ms=round((time.perf_counter() - started) * 1000),
        )
        raise

    usage_now = result.usage  # a RunUsage, not a method, in pydantic-ai 2.x
    audit.append(
        "agent_finished",
        agent=agent.name,
        delegated_by=delegated_by,
        ok=True,
        output=audit.summarise(result.output.model_dump() if hasattr(result.output, "model_dump") else result.output),
        requests=usage_now.requests,
        tokens=usage_now.total_tokens,
        ms=round((time.perf_counter() - started) * 1000),
    )
    return result

"""Shared construction for every agent on the team.

Each agent is the same four things: the one allowed model, the shop's MCP
tools, a prompt file, and a typed output. Building them through one function
keeps those four consistent and means a rule added to `prompts/_shared.md`
reaches every agent at once.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypeVar

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModelSettings

from .settings import PROMPTS_DIR, model
from .toolset import shop_tools

OutputT = TypeVar("OutputT")

#: The gateway refuses function tools on /v1/chat/completions unless reasoning
#: effort is off: "Function tools with reasoning_effort are not supported for
#: gpt-6-luna-global". Every agent on this team uses tools, so the setting is
#: applied once here rather than remembered at five call sites.
MODEL_SETTINGS = OpenAIChatModelSettings(openai_reasoning_effort="none")

#: Bounds one team run. Each tool round trip is a request, and a run that
#: touches three tickets through four specialists is perhaps 20–30; this leaves
#: headroom while stopping a loop from spending the budget.
MAX_REQUESTS_PER_RUN = 60


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
        toolsets=[shop_tools],
        output_type=output_type,
    )

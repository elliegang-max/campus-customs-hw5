"""Model and credentials — the one place a model client is built.

The assignment allows exactly one model, so exactly one function here knows how
to make one, and it refuses anything else. An agent cannot quietly name a
different model: there is no other way to get a client.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

#: The only model this assignment may use. Points are deducted for any other.
MODEL_NAME = "gpt-6-luna"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_env_file(path: Path) -> None:
    """Set any KEY=VALUE from a dotenv-style file that isn't already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        os.environ.setdefault(name.strip(), value.strip())


def _load_credentials() -> tuple[str, str]:
    """Portkey key and base URL: process env, then ./.env, then ~/.config."""
    _load_env_file(PROJECT_ROOT / ".env")
    _load_env_file(Path.home() / ".config" / "ai-keys" / "keys.env")

    key = os.environ.get("PORTKEY_API_KEY")
    base_url = os.environ.get("PORTKEY_BASE_URL")
    if not key or not base_url:
        raise RuntimeError(
            "PORTKEY_API_KEY and PORTKEY_BASE_URL must be set — see .env.example"
        )
    return key, base_url


@lru_cache(maxsize=1)
def _client() -> AsyncOpenAI:
    """One client for the whole team, pointed at the Portkey gateway."""
    key, base_url = _load_credentials()
    return AsyncOpenAI(
        base_url=base_url,
        api_key="unused",  # Portkey authenticates with its own header
        default_headers={"x-portkey-api-key": key},
        timeout=120.0,
        max_retries=2,
    )


@lru_cache(maxsize=1)
def model(name: str = MODEL_NAME) -> OpenAIChatModel:
    """The team's model. Refuses any name but `gpt-6-luna`."""
    if name != MODEL_NAME:
        raise ValueError(
            f"this assignment allows {MODEL_NAME!r} only, not {name!r} — "
            "every agent must use the same model"
        )
    return OpenAIChatModel(name, provider=OpenAIProvider(openai_client=_client()))

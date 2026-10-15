"""The audit trail: append-only, one record per step of an agent loop.

`output/audit_trail.json` is a JSON array that **grows**. Every run appends to
it; nothing ever rewrites or truncates what is already there, so the file is a
record of everything this system has ever done rather than a snapshot of the
last run.

What gets recorded, in the order it happens:

* `run_started` / `run_finished` — one per board run, with the instruction and
  the final token and request usage.
* `agent_started` / `agent_finished` — one per agent run, including every
  delegated one, so the delegation tree can be reconstructed afterwards.
* `delegation` — who asked whom, and what was asked.
* `tool_call` — every MCP tool call: which agent made it, the arguments, how
  long it took, and whether it succeeded or raised.

A refused payment is as interesting as a successful one, so failures are
recorded with their error text rather than dropped.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import PROJECT_ROOT

AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"

#: Ties every record from one board run together.
_run_id = uuid.uuid4().hex[:12]
_sequence = 0


def run_id() -> str:
    return _run_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(event: str, **fields: Any) -> dict[str, Any]:
    """Append one record. Never truncates the file.

    The whole array is read and rewritten because the file must stay valid
    JSON; the trail for this assignment is small enough that this costs
    nothing, and a half-written line can never leave it unparseable.
    """
    global _sequence
    _sequence += 1

    record = {
        "run_id": _run_id,
        "seq": _sequence,
        "at": _now(),
        "event": event,
        **fields,
    }

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if AUDIT_PATH.exists():
        try:
            loaded = json.loads(AUDIT_PATH.read_text() or "[]")
            if isinstance(loaded, list):
                existing = loaded
        except json.JSONDecodeError:
            # Never lose the trail to a parse error: keep the damaged file
            # beside the new one rather than overwriting it.
            AUDIT_PATH.rename(AUDIT_PATH.with_suffix(".json.corrupt"))

    existing.append(record)

    # Write beside the target and move into place, so an interrupted write
    # cannot leave a truncated trail.
    tmp = AUDIT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n")
    os.replace(tmp, AUDIT_PATH)
    return record


def summarise(value: Any, limit: int = 600) -> Any:
    """Keep a record readable without throwing away what it was."""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, default=str)
    else:
        text = str(value)
    if len(text) <= limit:
        return value if isinstance(value, (dict, list)) else text
    return text[:limit] + f"… ({len(text)} chars)"

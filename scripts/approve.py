"""The human's side of the approval loop.

Agents can propose a payment; only a person can approve one. That decision is
recorded through the same MCP server the agents use — there is no second path
to the database — but through the one tool their toolset filters out.

    ./.venv/bin/python scripts/approve.py --list
    ./.venv/bin/python scripts/approve.py 1 --by "Shutong Gang"
    ./.venv/bin/python scripts/approve.py 1 --by "Shutong Gang" --decline
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
MCP_JSON = ROOT / ".mcp.json"


def client_config() -> dict:
    config = json.loads(MCP_JSON.read_text())
    entry = config["mcpServers"]["campus-customs"]
    # Absolute, but without resolve(): .venv/bin/python is a symlink to the
    # system interpreter, which has no fastmcp.
    entry["command"] = str(ROOT / entry["command"])
    entry["cwd"] = str(ROOT)
    return config


def payload(result):
    return result.structured_content or json.loads(result.content[0].text)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("approval_id", nargs="?", type=int, help="The proposal to decide.")
    parser.add_argument("--by", help="Your name. Recorded against the payment.")
    parser.add_argument("--decline", action="store_true", help="Decline instead of approve.")
    parser.add_argument("--list", action="store_true", help="Show proposals and stop.")
    args = parser.parse_args()

    async with Client(client_config()) as client:
        if args.list or args.approval_id is None:
            data = payload(await client.call_tool("list_approvals", {}))
            if not data["approvals"]:
                print("no payment proposals on the board")
                return 0
            print(f"as of {data['today']}:\n")
            for a in data["approvals"]:
                decided = f" by {a['approved_by']}" if a["approved_by"] else ""
                print(
                    f"  [{a['id']}] {a['status']:9} {a['kind']:7} #{a['ref_id']} "
                    f"{a['amount']:>9.2f} from {a['account']}{decided}"
                )
                print(f"      {a['reason']}  (proposed by {a['requested_by']})")
            if args.approval_id is None:
                print("\nto approve:  scripts/approve.py <id> --by 'Your Name'")
            return 0

        if not args.by:
            parser.error("--by is required: an approval must record who gave it")

        decision = "declined" if args.decline else "approved"
        result = payload(
            await client.call_tool(
                "approve_payment",
                {
                    "approval_id": args.approval_id,
                    "approved_by": args.by,
                    "decision": decision,
                },
            )
        )
        print(
            f"approval {result['id']}: {result['status']} by {result['approved_by']} "
            f"on {result['decided_at']} — {result['kind']} #{result['ref_id']} "
            f"{result['amount']:.2f}"
        )
        print("the agents can now pay this, and only this.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

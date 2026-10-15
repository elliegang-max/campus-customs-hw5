"""Run the agent team over the board and print the Boss's review as JSON.

    ./.venv/bin/python -m backend.run_board                 # the whole board
    ./.venv/bin/python -m backend.run_board --ticket 102    # one ticket
    ./.venv/bin/python -m backend.run_board -o output/board_review.json

Read-only: the tools cannot write, and payments come back as approval requests
for a human. Reset the database with ./scripts/reset_db.sh before a full run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .boss import DEFAULT_INSTRUCTION, review_board


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ticket", type=int, help="Work a single ticket instead of the whole board."
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="Write the review to this file as JSON."
    )
    args = parser.parse_args()

    instruction = (
        f"Work ticket {args.ticket} only. Read it, delegate what you cannot settle "
        "yourself, and report what should happen with it."
        if args.ticket
        else DEFAULT_INSTRUCTION
    )

    review = asyncio.run(review_board(instruction))
    text = json.dumps(review.model_dump(), indent=2) + "\n"

    if args.output:
        args.output.write_text(text)
        print(f"written: {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

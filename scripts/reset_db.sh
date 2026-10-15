#!/usr/bin/env bash
# Reset the working database back to the pristine original.
#
# data/campus_customs.db      — the original pack, never written to
# data/campus_customs_new.db  — the working copy; tools write here
#
# Run from anywhere:  ./scripts/reset_db.sh
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$root/data/campus_customs.db"
dst="$root/data/campus_customs_new.db"

[ -f "$src" ] || { echo "error: original not found at $src" >&2; exit 1; }

cp "$src" "$dst"
chmod u+w "$dst"
echo "reset: $dst restored from the original"

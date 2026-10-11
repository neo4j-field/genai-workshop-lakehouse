#!/usr/bin/env bash
# Set one KEY=VALUE line in .env. Every other line stays as it is.
# If KEY exists, its line is replaced. If not, the line is added at the end.
#
# Usage:
#   databricks/env_set.sh KEY VALUE
#   some-command | databricks/env_set.sh KEY      # VALUE is read from stdin
#
# Reading from stdin keeps a secret out of the process list.
set -euo pipefail

KEY="${1:?usage: env_set.sh KEY [VALUE]   (VALUE is read from stdin when omitted)}"
if [ "$#" -ge 2 ]; then
  VALUE="$2"
else
  IFS= read -r VALUE || true
fi

ENV_FILE="${ENV_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env}"
[ -f "$ENV_FILE" ] || { echo "No $ENV_FILE. Run: cp .env.example .env" >&2; exit 1; }

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

# ENVIRON keeps backslashes in the value as they are.
KEY="$KEY" VALUE="$VALUE" awk '
  BEGIN { key = ENVIRON["KEY"]; val = ENVIRON["VALUE"]; done = 0 }
  index($0, key "=") == 1 { if (!done) { print key "=" val; done = 1 } ; next }
  { print }
  END { if (!done) print key "=" val }
' "$ENV_FILE" > "$TMP"

# Write through the existing file so its permissions stay the same.
cat "$TMP" > "$ENV_FILE"
echo "Set $KEY in $ENV_FILE"

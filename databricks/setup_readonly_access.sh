#!/usr/bin/env bash
# Give learners read-only access to the AutoFix schema. Admin run, after load_databricks.py.
#
# What it does, in order:
#   1. Creates a service principal (a non-human account) named workshop-readonly.
#      It reuses the account when one with that name exists.
#   2. Grants the principal read access: USE CATALOG on the catalog, and
#      USE SCHEMA + SELECT on the whole schema. It grants nothing else.
#   3. Lets the principal run SQL on your SQL warehouse (CAN_USE).
#   4. Lets the principal own access tokens (CAN_USE on token usage).
#   5. Creates a short-lived token for the principal. It saves the token in .env.
#      It skips this step when .env already holds a token ID. Use --revoke to remove it.
#
# Needs in .env: DATABRICKS_PROFILE, DATABRICKS_HTTP_PATH.
# Writes to .env: DATABRICKS_SP_APP_ID, DATABRICKS_SP_ID, DATABRICKS_TOKEN,
# DATABRICKS_TOKEN_ID. Every other line in .env stays as it is.
#
# Usage:
#   databricks/setup_readonly_access.sh [--name NAME] [--lifetime SECONDS]
#   databricks/setup_readonly_access.sh --revoke
#
#   --name      display name of the service principal (default: workshop-readonly)
#   --lifetime  token lifetime in seconds (default: 28800, eight hours)
#   --revoke    delete the token from the last run and clear it from .env
set -euo pipefail

NAME="workshop-readonly"
LIFETIME=28800
REVOKE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --name)     NAME="${2:?--name needs a value}"; shift 2 ;;
    --lifetime) LIFETIME="${2:?--lifetime needs a value}"; shift 2 ;;
    --revoke)   REVOKE=1; shift ;;
    *) echo "Unknown option: $1" >&2
       echo "Usage: $0 [--name NAME] [--lifetime SECONDS] | --revoke" >&2; exit 1 ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/.."
[ -f .env ] || { echo "No .env. Run: cp .env.example .env" >&2; exit 1; }
command -v databricks >/dev/null || { echo "Install the Databricks CLI first." >&2; exit 1; }
command -v jq >/dev/null || { echo "Install jq first." >&2; exit 1; }

set -a; source .env; set +a
: "${DATABRICKS_PROFILE:?Set DATABRICKS_PROFILE in .env first}"
: "${DATABRICKS_CATALOG:=lakehouse-workshop}"
: "${DATABRICKS_SCHEMA:=autofix_service}"
PROFILE="$DATABRICKS_PROFILE"
CATALOG="$DATABRICKS_CATALOG"
SCHEMA="$DATABRICKS_SCHEMA"

# Use your CLI login. The read-only token must not take over the CLI.
unset DATABRICKS_TOKEN

if [ "$REVOKE" = 1 ]; then
  : "${DATABRICKS_TOKEN_ID:?No DATABRICKS_TOKEN_ID in .env. There is no token to revoke.}"
  : "${DATABRICKS_SP_ID:?No DATABRICKS_SP_ID in .env.}"
  echo "Revoking the workshop token ($DATABRICKS_TOKEN_ID)."
  databricks token-management delete "$DATABRICKS_TOKEN_ID" --profile "$PROFILE"
  LEFT="$(databricks token-management list --profile "$PROFILE" -o json \
    | jq "[.[] | select(.owner_id == $DATABRICKS_SP_ID)] | length")"
  echo "Tokens still owned by the principal: $LEFT (expect 0)."
  "$HERE/env_set.sh" DATABRICKS_TOKEN "" >/dev/null
  "$HERE/env_set.sh" DATABRICKS_TOKEN_ID "" >/dev/null
  echo "Done. Run: set -a; source .env; set +a"
  exit 0
fi

: "${DATABRICKS_HTTP_PATH:?Set DATABRICKS_HTTP_PATH in .env first}"
WAREHOUSE_ID="${DATABRICKS_HTTP_PATH##*/}"

if [ -n "${DATABRICKS_TOKEN_ID:-}" ]; then
  TOKEN_PLAN="Keep the existing token (id $DATABRICKS_TOKEN_ID). Run --revoke to remove it."
else
  TOKEN_PLAN="Create a token that lasts $LIFETIME seconds and save it in .env"
fi

cat <<PLAN
Read-only access for the AutoFix workshop
  Workspace profile: $PROFILE
  Catalog and schema: $CATALOG.$SCHEMA
  SQL warehouse:     $WAREHOUSE_ID

  1. Create or reuse the service principal "$NAME"
  2. Grant USE CATALOG, USE SCHEMA, and SELECT (read only)
  3. Allow the principal to use the SQL warehouse
  4. Allow the principal to own tokens
  5. $TOKEN_PLAN

PLAN

databricks schemas get "$CATALOG.$SCHEMA" --profile "$PROFILE" >/dev/null 2>&1 \
  || { echo "Schema $CATALOG.$SCHEMA not found. Create the catalog and run databricks/load_databricks.py first." >&2; exit 1; }

echo "[1/5] Service principal"
EXISTING="$(databricks service-principals list --profile "$PROFILE" \
  --filter "displayName eq \"$NAME\"" -o json)"
if [ "$(echo "$EXISTING" | jq 'length')" -gt 0 ]; then
  SP_JSON="$(echo "$EXISTING" | jq '.[0]')"
  echo "      Reusing \"$NAME\"."
else
  SP_JSON="$(databricks service-principals create --profile "$PROFILE" -o json \
    --json "{\"displayName\":\"$NAME\",\"entitlements\":[{\"value\":\"databricks-sql-access\"}]}")"
  echo "      Created \"$NAME\" with the databricks-sql-access entitlement."
fi
SP_APP_ID="$(echo "$SP_JSON" | jq -r .applicationId)"
SP_ID="$(echo "$SP_JSON" | jq -r .id)"
[ -n "$SP_APP_ID" ] && [ "$SP_APP_ID" != "null" ] || { echo "No applicationId in the response." >&2; exit 1; }
"$HERE/env_set.sh" DATABRICKS_SP_APP_ID "$SP_APP_ID" >/dev/null
"$HERE/env_set.sh" DATABRICKS_SP_ID "$SP_ID" >/dev/null
echo "      Application ID: $SP_APP_ID (saved in .env)"

# Grant on the whole schema. A per-table grant that leaves out a referenced table
# drops that foreign key with no error. BROWSE alone hides the key constraints.
echo "[2/5] Grants"
databricks grants update catalog "$CATALOG" --profile "$PROFILE" \
  --json "{\"changes\":[{\"principal\":\"$SP_APP_ID\",\"add\":[\"USE_CATALOG\"]}]}" >/dev/null
echo "      USE CATALOG on $CATALOG"
databricks grants update schema "$CATALOG.$SCHEMA" --profile "$PROFILE" \
  --json "{\"changes\":[{\"principal\":\"$SP_APP_ID\",\"add\":[\"USE_SCHEMA\",\"SELECT\"]}]}" >/dev/null
echo "      USE SCHEMA and SELECT on $CATALOG.$SCHEMA"

# update-permissions adds one entry. It keeps the entries that exist.
echo "[3/5] SQL warehouse"
databricks warehouses update-permissions "$WAREHOUSE_ID" --profile "$PROFILE" \
  --json "{\"access_control_list\":[{\"service_principal_name\":\"$SP_APP_ID\",\"permission_level\":\"CAN_USE\"}]}" >/dev/null
echo "      CAN_USE on warehouse $WAREHOUSE_ID"

echo "[4/5] Token permission"
databricks token-management update-permissions --profile "$PROFILE" \
  --json "{\"access_control_list\":[{\"service_principal_name\":\"$SP_APP_ID\",\"permission_level\":\"CAN_USE\"}]}" >/dev/null
echo "      CAN_USE on tokens"

echo "[5/5] Token"
if [ -n "${DATABRICKS_TOKEN_ID:-}" ]; then
  echo "      Skipped. A workshop token exists (id $DATABRICKS_TOKEN_ID)."
  echo
  echo "Done. Steps 1 to 4 are applied again. The token is unchanged."
  exit 0
fi
RESP="$(databricks token-management create-obo-token "$SP_APP_ID" --profile "$PROFILE" -o json \
  --lifetime-seconds "$LIFETIME" --comment "workshop read-only")"
# Values come through stdin so the secret never shows in the process list.
echo "$RESP" | jq -r .token_value | "$HERE/env_set.sh" DATABRICKS_TOKEN >/dev/null
echo "$RESP" | jq -r .token_info.token_id | "$HERE/env_set.sh" DATABRICKS_TOKEN_ID >/dev/null
echo "      Token saved as DATABRICKS_TOKEN in .env. It replaces your login token."
echo "      Token ID saved as DATABRICKS_TOKEN_ID. It expires in $LIFETIME seconds."

echo
echo "Done. Load the new values into your shell:  set -a; source .env; set +a"

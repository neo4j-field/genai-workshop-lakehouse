"""Databricks helper for the federated finale.

The Databricks counterpart of bq.py: the warehouse rows live in Unity Catalog
(never migrated), queried live over a Databricks SQL warehouse. Connection,
catalog, and schema come from .env (DATABRICKS_SERVER_HOSTNAME,
DATABRICKS_HTTP_PATH, DATABRICKS_CATALOG, DATABRICKS_SCHEMA).

Auth: DATABRICKS_TOKEN, the workshop's read-only token. Never commit it.
"""

import os
from typing import Any

from databricks import sql
from dotenv import load_dotenv

load_dotenv(override=True)

REQUIRED = ("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN")
CATALOG = os.environ.get("DATABRICKS_CATALOG") or "lakehouse-workshop"
SCHEMA = os.environ.get("DATABRICKS_SCHEMA") or "autofix_service"

# Tags workshop traffic in the warehouse query history.
USER_AGENT = "neo4j-genai-workshop-lakehouse"


def table(name: str) -> str:
    """Fully-qualified table reference, each part backtick-quoted.

    Spark SQL reads one backtick pair as one identifier, so the hyphenated
    catalog needs its own quotes: `lakehouse-workshop`.`autofix_service`.`parts`.
    """
    return f"`{CATALOG}`.`{SCHEMA}`.`{name}`"


def dbx_query(sql_text: str, params: dict[str, Any] | None = None) -> list[dict]:
    """Run a Databricks SQL query; return a list of dict rows.

    Parameters, if any, pass straight to the connector, which binds them
    natively as :name markers. The connection settings are checked here, not
    on import, so run_sql.py --info works before the token is set.
    """
    if missing := [name for name in REQUIRED if not os.environ.get(name)]:
        raise SystemExit(
            f"WAREHOUSE=databricks needs these set in .env: {', '.join(missing)}"
        )
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
        user_agent_entry=USER_AGENT,
    ) as conn, conn.cursor() as cur:
        cur.execute(sql_text, params or None)
        return [row.asDict() for row in cur.fetchall()]

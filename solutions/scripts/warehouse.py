"""Pick the warehouse the finale queries: Databricks or BigQuery.

WAREHOUSE in .env selects it (default databricks). Both sides expose the same two
functions:

  query(sql, params=None)  run SQL, return a list of dict rows
  table(name)              a fully-qualified, backtick-quoted table reference

The SQL dialect differs, and so do params. BigQuery binds @name markers as
STRING or ARRAY<STRING>. Databricks binds :name markers and infers each type.
Callers that pass params write the marker for the active warehouse.

Only the chosen side is imported, so a BigQuery learner needs no Databricks
settings and a Databricks learner needs no GCP settings.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

WAREHOUSES = ("databricks", "bigquery")
WAREHOUSE = (os.environ.get("WAREHOUSE") or "databricks").strip().lower()

if WAREHOUSE == "databricks":
    from dbx import dbx_query as query, table
elif WAREHOUSE == "bigquery":
    from bq import bq_query as query, table
else:
    raise SystemExit(
        f"WAREHOUSE={WAREHOUSE!r} is not valid. Set it to one of: "
        f"{', '.join(WAREHOUSES)}"
    )

__all__ = ["WAREHOUSE", "query", "table"]

r"""Run a warehouse SQL statement using the workshop's auth.

The agent writes Text2SQL grounded by the `connections` MCP schema, then runs it
here. WAREHOUSE in .env picks the warehouse (default bigquery); warehouse.py
loads its auth. On BigQuery that is the read-only key in BIGQUERY_SA_KEY_B64 if
set, otherwise your own gcloud login. Use this rather than the `bq` CLI, which
does not read the workshop key. On Databricks it is DATABRICKS_TOKEN.

Run with --info first to see which warehouse answers, its SQL dialect, and how
to write a table reference. The two warehouses quote names differently:

  BigQuery (GoogleSQL):         `PROJECT.DATASET.vehicles`
  Databricks (Databricks SQL):  `CATALOG`.`SCHEMA`.`vehicles`

Usage:
  python skill/scripts/run_sql.py --info
  python skill/scripts/run_sql.py "SELECT model, COUNT(*) AS n
                                    FROM \`PROJECT.DATASET.vehicles\` GROUP BY model"
"""

import json
import sys

from warehouse import WAREHOUSE, query, table

DIALECTS = {"bigquery": "GoogleSQL", "databricks": "Databricks SQL"}

if len(sys.argv) < 2:
    sys.exit('usage: run_sql.py "<SQL>"  |  run_sql.py --info')

if sys.argv[1] == "--info":
    print(f"warehouse: {WAREHOUSE}")
    print(f"dialect:   {DIALECTS[WAREHOUSE]}")
    print(f"table:     {table('<table>')}")
    sys.exit(0)

rows = query(sys.argv[1])
print(json.dumps(rows, indent=2, default=str))
print(f"\n{len(rows)} rows", file=sys.stderr)

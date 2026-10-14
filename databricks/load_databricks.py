"""Create the AutoFix warehouse in Databricks Unity Catalog and load it.

The schema lives in databricks/schema.sql, the twin of bigquery/schema.sql: six
Delta tables with informational PRIMARY KEY / FOREIGN KEY constraints (Unity
Catalog surfaces these in information_schema - the join paths the connections
shape reads). Data comes from sources/warehouse/*.csv.

Idempotent: CREATE ... IF NOT EXISTS + INSERT OVERWRITE, so re-running resets
the rows without dropping the schema.

Env (a .env is loaded if present):
  DATABRICKS_SERVER_HOSTNAME   e.g. dbc-xxxx.cloud.databricks.com   (no https://)
  DATABRICKS_HTTP_PATH         e.g. /sql/1.0/warehouses/abc123
  DATABRICKS_TOKEN             a PAT (dapi...) or OAuth token
  DATABRICKS_CATALOG           default: lakehouse-workshop
  DATABRICKS_SCHEMA            default: autofix_service

Run:  python databricks/load_databricks.py
"""

import csv
import os
from pathlib import Path

from dotenv import load_dotenv
from databricks import sql

load_dotenv(override=True)

HOST = os.environ["DATABRICKS_SERVER_HOSTNAME"]
HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
TOKEN = os.environ["DATABRICKS_TOKEN"]
CATALOG = os.environ.get("DATABRICKS_CATALOG") or "lakehouse-workshop"
SCHEMA = os.environ.get("DATABRICKS_SCHEMA") or "autofix_service"
FQ = f"`{CATALOG}`.`{SCHEMA}`"  # backticked so hyphenated catalog names work


def t(name):
    """Backtick-quoted fully-qualified table name."""
    return f"{FQ}.`{name}`"
SRC = Path(__file__).resolve().parent.parent / "sources" / "warehouse"

# column name -> type tag, in CSV order, per table
TABLES = {
    "vehicles": [("vin", "str"), ("make", "str"), ("model", "str"), ("year", "int"), ("engine", "str")],
    "dtc_codes": [("code", "str"), ("description", "str")],
    "procedures": [("procedure_id", "str"), ("name", "str"), ("labor_hours", "float")],
    "parts": [("part_number", "str"), ("name", "str"), ("superseded_by", "str")],
    "work_orders": [("wo_id", "str"), ("vin", "str"), ("opened", "date"), ("odometer", "int"),
                    ("complaint", "str"), ("dtc_code", "str"), ("procedure_id", "str"), ("comeback", "bool")],
    "work_order_parts": [("wo_id", "str"), ("part_number", "str"), ("qty", "int")],
}

SCHEMA_SQL = Path(__file__).resolve().parent / "schema.sql"


def split_statements(script):
    """Split a SQL script on semicolons that sit outside quotes and -- comments."""
    statements, current = [], []
    quote = None
    chars = iter(script)
    for ch in chars:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", "`"):
            quote = ch
            current.append(ch)
        elif ch == "-" and current[-1:] == ["-"]:
            current.pop()
            for skipped in chars:  # drop the rest of the comment line
                if skipped == "\n":
                    break
            current.append("\n")
        elif ch == ";":
            statements.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    statements.append("".join(current).strip())
    return [stmt for stmt in statements if stmt]


def schema_statements():
    """The statements of schema.sql with ${CATALOG} and ${SCHEMA} filled in."""
    script = SCHEMA_SQL.read_text().replace("${CATALOG}", CATALOG).replace("${SCHEMA}", SCHEMA)
    return split_statements(script)


def lit(value, tag):
    """Format a CSV string as a SQL literal for its column type."""
    if value is None or value == "":
        return "NULL"
    if tag == "str":
        return "'" + value.replace("'", "''") + "'"
    if tag == "int":
        return str(int(value))
    if tag == "float":
        return str(float(value))
    if tag == "bool":
        return "TRUE" if str(value).strip().lower() in ("true", "1", "t", "yes") else "FALSE"
    if tag == "date":
        return f"DATE'{value}'"
    raise ValueError(tag)


def load_rows(cur, table, cols):
    rows = list(csv.DictReader(open(SRC / f"{table}.csv")))
    names = [c for c, _ in cols]
    values = ",\n".join(
        "(" + ", ".join(lit(r[c], t) for c, t in cols) + ")" for r in rows
    )
    cur.execute(f"INSERT OVERWRITE {FQ}.{table} ({', '.join(names)}) VALUES\n{values}")
    return len(rows)


def main():
    print(f"Connecting to {HOST} -> {FQ}")
    with sql.connect(server_hostname=HOST, http_path=HTTP_PATH, access_token=TOKEN) as conn:
        with conn.cursor() as cur:
            for stmt in schema_statements():
                cur.execute(stmt)
            print(f"Schema ready ({SCHEMA_SQL.name}: 6 tables, PK/FK constraints).")
            total = 0
            for table, cols in TABLES.items():
                n = load_rows(cur, table, cols)
                total += n
                print(f"  loaded {table}: {n} rows")
    print(f"Done: {FQ} loaded ({total} rows).")


if __name__ == "__main__":
    main()

"""Build the connections graph: the warehouse's metadata plus a few example
values per column.

Runs neocarta's BigQuery schema connector against the AutoFix warehouse and
writes the metadata graph (Database -> Schema -> Table -> Column, with
Column-[:REFERENCES]->Column from the foreign keys) into your Neo4j sandbox.

This is the connections shape: the join-path map an agent reads to route a
question to the right tables and write correct SQL. The warehouse *rows* stay
in the warehouse. Only this metadata and a few example values per column
cross over.

Connection + dataset come from .env:
  NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE
  GCP_PROJECT_ID        (billing project; the shared workshop project)
  BIGQUERY_DATASET_ID   (defaults to autofix_service)
  BIGQUERY_SA_KEY_B64   (the workshop read-only key from the slides; if unset,
                         your own gcloud login is used)

WAREHOUSE=databricks reads a Unity Catalog schema instead, with neocarta's
Databricks schema connector. It needs DATABRICKS_SERVER_HOSTNAME /
DATABRICKS_HTTP_PATH / DATABRICKS_TOKEN, and DATABRICKS_CATALOG /
DATABRICKS_SCHEMA name the schema (default lakehouse-workshop.autofix_service).

Run:  python load/build_connections.py
"""

import base64
import json
import os
import types

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery
from neo4j import GraphDatabase

from neocarta.connectors.bigquery import BigQuerySchemaConnector

load_dotenv(override=True)

PROJECT = os.environ["GCP_PROJECT_ID"]
DATASET = os.environ.get("BIGQUERY_DATASET_ID", "autofix_service")
WAREHOUSES = ("bigquery", "databricks")
WAREHOUSE = (os.environ.get("WAREHOUSE") or "bigquery").strip().lower()


def bq_client(project):
    """Workshop read-only service account if BIGQUERY_SA_KEY_B64 is set,
    otherwise your own gcloud credentials."""
    b64 = os.environ.get("BIGQUERY_SA_KEY_B64")
    if b64:
        from google.oauth2 import service_account
        info = json.loads(base64.b64decode(b64))
        creds = service_account.Credentials.from_service_account_info(info)
        return bigquery.Client(project=project, credentials=creds)
    return bigquery.Client(project=project)


def build_databricks(driver, database):
    """Read the Unity Catalog schema's metadata over a Databricks SQL warehouse."""
    from databricks import sql
    from neocarta.connectors.databricks import DatabricksSchemaConnector

    required = ("DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN")
    if missing := [name for name in required if not os.environ.get(name)]:
        raise SystemExit(
            f"WAREHOUSE=databricks needs these set in .env: {', '.join(missing)}"
        )
    catalog = os.environ.get("DATABRICKS_CATALOG") or "lakehouse-workshop"
    schema = os.environ.get("DATABRICKS_SCHEMA") or "autofix_service"

    print(f"Reading {catalog}.{schema} metadata -> Neo4j ({database})...")
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
        user_agent_entry="neo4j-genai-workshop-lakehouse",
    ) as connection:
        connector = DatabricksSchemaConnector(
            connection=connection,
            catalog=catalog,
            neo4j_driver=driver,
            database_name=database,
        )
        connector.ingest(schema=schema)

    # Count only the schema just built. A missing grant drops a foreign key with
    # no error, so a short REFERENCES count is the only sign of it.
    with driver.session(database=database) as s:
        counts = s.run(
            "MATCH (:Database {name: $catalog})-[:HAS_SCHEMA]->(:Schema {name: $schema})"
            "-[:HAS_TABLE]->(t:Table) "
            "OPTIONAL MATCH (t)-[:HAS_COLUMN]->(:Column)-[r:REFERENCES]->(:Column) "
            "RETURN count(DISTINCT t) AS tables, count(r) AS refs",
            catalog=catalog,
            schema=schema,
        ).single()
    print(
        f"Connections graph ready: {counts['tables']} tables, "
        f"{counts['refs']} REFERENCES (join paths)."
    )


def main():
    if WAREHOUSE not in WAREHOUSES:
        raise SystemExit(
            f"WAREHOUSE={WAREHOUSE!r} is not valid. Set it to one of: "
            f"{', '.join(WAREHOUSES)}"
        )
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    if WAREHOUSE == "databricks":
        try:
            build_databricks(driver, database)
        finally:
            driver.close()
        print("Your agent reads this through the connections MCP (get_full_metadata_schema).")
        return
    try:
        client = bq_client(PROJECT)

        print(f"Reading {PROJECT}.{DATASET} metadata -> Neo4j ({database})...")
        # Schema only — no embeddings (the FK graph is the join map; the warehouse has six tables.
        connector = BigQuerySchemaConnector(
            client=client,
            project_id=PROJECT,
            neo4j_driver=driver,
            database_name=database,
        )

        # Skip a sub-step the workshop key can't run without project-wide metadata permissions.
        def _bypass_extract_schema_info(self, dataset_id=None, cache=True):
            """
            Bypass project-wide metaDataViewer permissions in GCP. BQ roles for demos and workshops are dataset specific,
            but schema info extraction in GCP now requires broader project-wide permissions.
            """
            dataset_id = self._get_dataset_id(dataset_id)
            df = pd.DataFrame([{"project_id": self.project_id, "dataset_id": dataset_id,
                                "description": "AutoFix Group service warehouse (workshop sample)", }])
            if cache: self._cache["schema_info"] = df
            return df

        connector.extractor.extract_schema_info = types.MethodType(
            _bypass_extract_schema_info, connector.extractor
        )

        # Run neocarta ingest
        connector.ingest(dataset_id=DATASET)

        with driver.session(database=database) as s:
            refs = s.run("MATCH (:Column)-[r:REFERENCES]->(:Column) RETURN count(r) AS n").single()["n"]
            tables = s.run("MATCH (t:Table) RETURN count(t) AS n").single()["n"]
    finally:
        driver.close()
    print(f"Connections graph ready: {tables} tables, {refs} REFERENCES (join paths).")
    print("Your agent reads this through the connections MCP (get_full_metadata_schema).")


if __name__ == "__main__":
    main()

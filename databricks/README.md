# Instructor Guide: Set Up AutoFix on Databricks

This guide is for the **instructor or workshop admin**. Learners do not follow it.
Learners receive three values from you and paste them into their own `.env`.

The workshop's default backend is Databricks plus Neo4j. This guide stands the
AutoFix data up on Databricks. Part 1 is the main path. Part 2 is optional.

## Overview

- **Who uses this guide:** The instructor or admin. You need rights to create a catalog, grant access, and create a service principal in the workspace.
- **What learners get:** The workspace host, the SQL warehouse HTTP path, and a read-only token. `.env.example` already sets `WAREHOUSE=databricks`, the default.
- **Part 1, main path:** You load six warehouse tables and hand out read-only access. Learners build the connections graph and query the rows live. Most workshops need only this part.
- **Part 2, optional path:** You expose the data to a coding agent through Databricks managed MCP. **Genie** answers questions over the tables. **AI Search** searches the document PDFs. This part bills while it runs.
- **Unity Catalog:** The Databricks system that holds catalogs, schemas, and tables, and controls who can read them.
- **SQL warehouse:** The Databricks compute that runs SQL. Every learner query runs on it.
- **Service principal:** A non-human account. The learners' read-only token belongs to one.
- **Token:** A secret string that proves who is calling. Never commit one to git.

## Before you start

You need these on your own machine:

- **Databricks CLI:** Version 1.0 or later. Sign in with `databricks auth login --host <workspace-url> --profile <name>`. This makes an OAuth profile. The CLI ignores `DATABRICKS_TOKEN` for an OAuth profile, so the token in `.env` never takes over your CLI login.
- **jq:** A small tool that reads JSON. The commands below use it.
- **A SQL warehouse:** A running one in the workspace.
- **Admin rights:** You can create a catalog, grant access, and create a service principal.

Every command runs from the repo root. Values in angle brackets, like
`<warehouse-id>`, are placeholders. Replace them with your own values.

---

# Part 1: The main path (WAREHOUSE=databricks)

## Step 1: Create the Python environment

The whole repo shares one `.venv`. Databricks does not need its own.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "from databricks import sql; print('ok')"
```

Expect `ok`.

- **What gets installed:** `requirements.txt` installs `databricks-sql-connector` and `databricks-sdk` through `neocarta[databricks]`. It installs `python-dotenv` directly.
- **Shortcut:** `./.devcontainer/post-create-local.sh` creates `.venv` and installs `requirements.txt`. It also installs the Neo4j CLI.
- **Codespace:** `post-create.sh` has already installed everything. Skip the `venv` lines and run only the `python -c` check.

## Step 2: Set up `.env`

All settings live in `.env`. The Databricks section of `.env.example` lists the values
learners use. The instructor-only values are not in that file. This step tells you which
ones to add.

```bash
cp .env.example .env     # skip this if .env already exists
```

Open `.env` and set these values:

- **`WAREHOUSE`:** Set it to `databricks`.
- **`DATABRICKS_PROFILE`:** The name of your Databricks CLI profile. Add this line yourself, because `.env.example` does not include it. Run `databricks auth profiles` to list your profiles.
- **`DATABRICKS_SERVER_HOSTNAME`:** The workspace host, for example `dbc-xxxx.cloud.databricks.com`. Write it without `https://`.
- **`DATABRICKS_HTTP_PATH`:** Set it to `/sql/1.0/warehouses/<warehouse-id>`. Run `databricks warehouses list --profile <your-profile>` to find the warehouse ID.
- **`DATABRICKS_CATALOG` and `DATABRICKS_SCHEMA`:** The defaults are `lakehouse-workshop` and `autofix_service`. Set other names here, for example `lakehouse-workshop-test`. Every command below reads these two variables, so you change nothing else.
- **Values the scripts fill in:** Leave `DATABRICKS_TOKEN` empty. Step 4 and Step 5 set it. Do not add `DATABRICKS_SP_APP_ID`, `DATABRICKS_SP_ID`, or `DATABRICKS_TOKEN_ID`. The Step 5 script adds them to `.env`.

Then copy every `.env` value into your shell:

```bash
set -a; source .env; set +a
```

- **Why this matters:** The Python scripts read `.env` themselves, and `.env` beats the shell. After this line the shell and `.env` hold the same values.
- **When to run it again:** Run it in every new terminal. Run it after any step that changes `.env`. Each of those steps ends with this line.

Optional: `test_connection.ipynb` is a quick notebook that checks your `.env` connection.

## Step 3: Create the catalog

The loader creates the schema and tables. It does not create the catalog.
This command creates the catalog named in `DATABRICKS_CATALOG` and runs on your SQL warehouse:

```bash
databricks experimental aitools tools query "CREATE CATALOG IF NOT EXISTS \`$DATABRICKS_CATALOG\`" \
  --profile "$DATABRICKS_PROFILE" --warehouse "${DATABRICKS_HTTP_PATH##*/}"
```

- **Safe to repeat:** `IF NOT EXISTS` skips a catalog that exists.
- **Warehouse ID:** `${DATABRICKS_HTTP_PATH##*/}` is the last part of your HTTP path.

## Step 4: Load the six tables

**Optional: start from scratch.** Do this when the schema exists from an earlier run.
The loader never changes the comment on an existing schema or table, so an old
schema keeps its old comments. Drop the schema first:

```bash
databricks experimental aitools tools query "DROP SCHEMA IF EXISTS \`$DATABRICKS_CATALOG\`.\`$DATABRICKS_SCHEMA\` CASCADE" \
  --profile "$DATABRICKS_PROFILE" --warehouse "${DATABRICKS_HTTP_PATH##*/}"
```

- **What it deletes:** Every table in the schema. It also deletes the Volume and index tables from Part 2.
- **Grants:** They go with the schema. Run Step 5 again after the load to restore them.
- **Fresh workspace:** Skip this. `IF EXISTS` makes the command safe, but there is nothing to drop.

Then put your own login token in `.env`. It lasts about one hour. Run the loader.

```bash
databricks auth token --profile "$DATABRICKS_PROFILE" -o json | jq -r .access_token \
  | ./databricks/env_set.sh DATABRICKS_TOKEN
set -a; source .env; set +a
python databricks/load_databricks.py
```

- **Schema file:** [`schema.sql`](schema.sql) defines the schema, the six tables, the keys, and every comment. It is the Databricks twin of [`bigquery/schema.sql`](../bigquery/schema.sql). The tables, columns, comments, and foreign key names are the same. Only the SQL dialect differs.
- **What the loader does:** It runs `schema.sql` with your catalog and schema names filled in. Then it loads the rows from `sources/warehouse/*.csv`.
- **What it creates:** The schema and six Delta tables in `{catalog}.{schema}`. The primary and foreign keys become the join paths in the connections graph.
- **Safe to repeat:** Running it again resets the rows.

## Step 5: Create the read-only access

One script sets up everything the learners need. Run it as yourself.

```bash
./databricks/setup_readonly_access.sh --lifetime 28800
set -a; source .env; set +a
```

`--lifetime` is the token life in seconds. Use `3600` for one hour or `28800` for
eight hours. The default is `28800`.

The script prints its plan, then runs five steps:

1. **Service principal:** It creates a service principal named `workshop-readonly` with the `databricks-sql-access` entitlement. That entitlement lets the account run SQL. If the name exists, the script reuses it.
2. **Grants:** It gives the principal `USE CATALOG` on the catalog, and `USE SCHEMA` and `SELECT` on the whole schema. It grants nothing else. The principal cannot write, create, or drop anything.
3. **Warehouse access:** It gives the principal `CAN_USE` on your SQL warehouse. The warehouse ID comes from `DATABRICKS_HTTP_PATH`. Existing permissions stay.
4. **Token permission:** It gives the principal `CAN_USE` on tokens, so it can own one.
5. **Token:** It creates a token for the principal and saves it in `.env`. The token expires after `--lifetime` seconds.

The script sets these lines in `.env`. It adds a line that is missing:

- **`DATABRICKS_SP_APP_ID` and `DATABRICKS_SP_ID`:** The IDs of the service principal.
- **`DATABRICKS_TOKEN`:** The read-only token. It replaces your login token.
- **`DATABRICKS_TOKEN_ID`:** The token ID. The revoke step uses it.
- **Every other line:** It stays as it was.

Two more facts about the script:

- **Safe to repeat:** Steps 1 to 4 apply again with no harm. Step 5 skips when `.env` already holds a token ID. One token is shared by all learners.
- **Why the whole schema:** A per-table grant that leaves out a referenced table drops that foreign key with no error. The join path then disappears from the graph. `BROWSE` alone hides the key constraints, so neocarta builds no join paths.

Size the SQL warehouse for the class. Nobody has tested many learners on one warehouse.

## Step 6: Check the setup as a learner

`.env` now holds the learner settings. Run the same commands a learner runs.

```bash
python load/build_connections.py
python skill/scripts/run_sql.py --info
python skill/scripts/run_sql.py "SELECT count(DISTINCT w.wo_id) AS work_orders, count_if(w.comeback) AS comebacks
  FROM \`$DATABRICKS_CATALOG\`.\`$DATABRICKS_SCHEMA\`.\`work_orders\` w
  JOIN \`$DATABRICKS_CATALOG\`.\`$DATABRICKS_SCHEMA\`.\`vehicles\` v ON w.vin = v.vin
  WHERE v.model = 'Falcon' AND v.engine = '2.0T' AND w.dtc_code = 'P0301'"
```

Expect these results:

- **Build:** `Connections graph ready: 6 tables, 5 REFERENCES (join paths).` Fewer than 5 means a grant is missing. Run Step 5 again.
- **Info:** `warehouse: databricks`, and the table form `` `<catalog>`.`<schema>`.`<table>` `` with your catalog and schema names.
- **Counts:** 29 work orders and 6 comebacks. BigQuery gives the same numbers.

`build_connections.py` writes to the Neo4j instance in `.env`. Build only one warehouse into each Neo4j instance, because the path tool reads join paths from every database.

## Step 7: Hand out the values

Print the three values to give each learner:

```bash
grep -E '^DATABRICKS_(SERVER_HOSTNAME|HTTP_PATH|TOKEN)=' .env
```

Each learner sets these in the Databricks section of their own `.env`:

```
WAREHOUSE=databricks
DATABRICKS_SERVER_HOSTNAME=<host>
DATABRICKS_HTTP_PATH=<http-path>
DATABRICKS_TOKEN=<token>
```

- **Catalog and schema:** `.env.example` already sets both to the workshop defaults. If you use other names, add `DATABRICKS_CATALOG` and `DATABRICKS_SCHEMA` to the values you hand out.
- **Query tag:** Every learner query carries the tag `neo4j-genai-workshop-lakehouse`. Search for it in the warehouse query history.

### Optional: test the hand-out as a learner

Step 6 ran with your `.env`, which holds instructor-only values. This test runs the
same checks from a fresh checkout that has only the values a learner receives. If it
passes, a learner has everything they need.

1. Make a fresh checkout in a new folder:

   ```bash
   git clone <repo-url> autofix-learner-test
   cd autofix-learner-test
   cp .env.example .env
   ```

2. Copy these values from your `.env` into the new `.env`:

   - `WAREHOUSE=databricks`
   - `NEO4J_URI`
   - `NEO4J_USERNAME`
   - `NEO4J_PASSWORD`
   - `NEO4J_DATABASE`
   - `DATABRICKS_SERVER_HOSTNAME`
   - `DATABRICKS_HTTP_PATH`
   - `DATABRICKS_TOKEN`
   - `DATABRICKS_CATALOG` and `DATABRICKS_SCHEMA`, only if you use names other than the defaults

   Do not copy `DATABRICKS_PROFILE`, `DATABRICKS_SP_APP_ID`, `DATABRICKS_SP_ID`, or `DATABRICKS_TOKEN_ID`. Learners do not receive them.

3. Set up the environment and run the checks:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   set -a; source .env; set +a

   python load/build_connections.py
   python skill/scripts/run_sql.py --info
   python skill/scripts/run_sql.py "SELECT count(*) AS vehicles FROM \`$DATABRICKS_CATALOG\`.\`$DATABRICKS_SCHEMA\`.\`vehicles\`"
   ```

- **Expected results:** The same as Step 6. The build prints `6 tables, 5 REFERENCES`. The info command prints `warehouse: databricks`. The count prints a number above 0.
- **Failure:** A missing value in the hand-out shows here as an error. Add the value to the hand-out and run the test again.
- **Cleanup:** Delete the `autofix-learner-test` folder when you finish. Its `.env` holds the learners' token.

## Step 8: Revoke the token after the workshop

```bash
./databricks/setup_readonly_access.sh --revoke
set -a; source .env; set +a
```

- **Delete:** It deletes the token that Step 5 created.
- **Check:** It counts the tokens the principal still owns. Expect `0`.
- **Clear:** It empties `DATABRICKS_TOKEN` and `DATABRICKS_TOKEN_ID` in `.env`. Every other line stays.
- **Re-source:** The last line clears the token from your shell.
- **What stays:** The service principal and its grants stay. Delete the schema to remove the grants, or run Step 5 for the next workshop.

---

# Part 2: Optional Genie and AI Search

## Overview

- **Purpose:** Part 2 builds the comparison case for the workshop's main idea, that context comes in shapes, not queries. It sets up a Databricks-native agent that has no graph shape. **AI Search** finds document passages by similarity. **Genie** answers questions over the six tables.
- **Who uses it:** Only an instructor or demo author runs Part 2. Learners never run it. No workshop module and no skill script reads the AI Search index or the Genie space.
- **What it shows:** The comparison gives two results, listed below.
- **Similarity retrieval only samples the corpus:** A similarity search returns the passages closest to the question. The agent sees a slice of the library, and the agent itself flags the coverage gaps in what it found.
- **The graph covered and clustered all 112 docs:** The document graph gives the agent a table of contents and Leiden themes. For a question such as "common patterns across our bulletins and recalls", the graph covers and groups every document.
- **A lack-of-shape effect:** The difference comes from the missing shape. Any similarity-only retriever returns top matches and cannot show the whole library.
- **Vendor-neutral:** The comparison is not a criticism of Databricks. AI Search and Genie do their jobs well. A question about the whole library needs a map of the library, and a search box does not provide one.

Skip this part unless you want a coding agent to use Databricks managed MCP. The
agent then asks Genie about the tables and AI Search about the PDFs.

## Part 2 prerequisites

- **Workspace features:** Unity Catalog, a running SQL warehouse, **AI Search** with an embedding endpoint such as `databricks-gte-large-en`, **managed MCP** in Public Preview, and a **Genie space**. A served chat model such as `databricks-claude-sonnet-4-5` is also needed.
- **Extra package:** `pip install databricks-vectorsearch`. `requirements.txt` does not install it. Only `build_doc_index.py` and the teardown need it.
- **Your own login token:** Run the token line from Step 4 first. It replaces the read-only token in `.env` with your login token. The read-only token cannot create tables or indexes. Part 2 leaves your login token in `.env`. If you do Part 2 after Step 5, run Step 8 and then Step 5 again before Step 7, so `.env` holds a read-only token again.
- **Optional settings:** Add these lines to `.env` only to change a default. `.env.example` does not include them. `DATABRICKS_VOLUME` (default `pdfs`), `DATABRICKS_VS_ENDPOINT` (default `autofix-search`), and `DATABRICKS_EMBED_ENDPOINT` (default `databricks-gte-large-en`).

## Step 9: Upload the PDFs

```bash
python databricks/upload_pdfs.py
```

It creates the Unity Catalog Volume `{catalog}.{schema}.pdfs` and uploads the AutoFix PDFs.

## Step 10: Build the AI Search index

```bash
python databricks/build_doc_index.py
```

- **What it does:** It parses the PDFs with `ai_parse_document`, writes `doc_chunks`, then creates an AI Search endpoint and a Delta Sync index. The index embeds each chunk with `databricks-gte-large-en`.
- **Time and cost:** It creates infrastructure. It takes 10 to 20 minutes and bills.

## Step 11: Create the managed MCP tools

The agent reaches both tools at `/api/2.0/mcp/...`.

- **AI Search MCP:** Ready once the index is live. The URL is `https://<host>/api/2.0/mcp/ai-search/<catalog>/<schema>/doc_chunks_idx`, with your catalog and schema names.
- **Genie space MCP:** Create a Genie space in the Databricks UI. Limit it to the six tables: `vehicles`, `work_orders`, `work_order_parts`, `parts`, `procedures`, `dtc_codes`. Copy its `space_id`. The URL is `https://<host>/api/2.0/mcp/genie/<space_id>`.
- **Managed MCP switch:** Ask a workspace admin to confirm it is enabled.

## Step 12: Connect the tools to the coding agent

These commands save the token in your user settings, so it never lands in the repo.
The URL reads your host, catalog, and schema from `.env`. Replace `<space_id>` and `<PAT>`.

```bash
claude mcp add --transport http databricks-aisearch \
  "https://$DATABRICKS_SERVER_HOSTNAME/api/2.0/mcp/ai-search/$DATABRICKS_CATALOG/$DATABRICKS_SCHEMA/doc_chunks_idx" \
  --header "Authorization: Bearer <PAT>"

claude mcp add --transport http databricks-genie \
  "https://$DATABRICKS_SERVER_HOSTNAME/api/2.0/mcp/genie/<space_id>" \
  --header "Authorization: Bearer <PAT>"
```

Start the agent and approve both servers when it asks. A personal access token is
the simplest way to start. OAuth is the preferred managed-MCP login.

---

# Teardown

## Stop AI Search billing

The AI Search endpoint bills while it runs. Delete it when you finish Part 2:

```python
import os

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient(
    workspace_url=f"https://{os.environ['DATABRICKS_SERVER_HOSTNAME']}",
    personal_access_token=os.environ["DATABRICKS_TOKEN"],
    disable_notice=True,
)
index = f"{os.environ['DATABRICKS_CATALOG']}.{os.environ['DATABRICKS_SCHEMA']}.doc_chunks_idx"
vsc.delete_index(endpoint_name="autofix-search", index_name=index)
vsc.delete_endpoint("autofix-search")
```

Run it with your login token in `.env`, as in Step 4.

## Remove everything

- **Drop the schema:** Run the `DROP SCHEMA` command from Step 4. It drops the tables, the Volume, and the parsed and chunk tables.
- **Remove the MCP servers:** Run `claude mcp remove databricks-aisearch databricks-genie`.
- **Revoke the learners' token:** Follow Step 8.

---

## Files

| File | Role |
|---|---|
| `test_connection.ipynb` | Checks your `.env` connection |
| `env_set.sh` | Sets one `KEY=VALUE` line in `.env` and keeps every other line |
| `schema.sql` | Defines the schema, six tables, keys, and comments. The twin of `bigquery/schema.sql` |
| `setup_readonly_access.sh` | Creates the read-only service principal, grants, warehouse access, and token |
| `load_databricks.py` | Runs `schema.sql`, then loads the CSV rows into the six tables |
| `upload_pdfs.py` | Uploads the PDFs to a Unity Catalog Volume |
| `build_doc_index.py` | Parses the PDFs, makes chunks, and builds the AI Search endpoint and index |
| `README.md` | This guide |

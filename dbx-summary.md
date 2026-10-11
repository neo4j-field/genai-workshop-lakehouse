# Databricks Support: Summary

## Overview

The workshop now runs on Databricks as well as BigQuery. One setting in `.env`, `WAREHOUSE`, picks the warehouse. `WAREHOUSE=bigquery` is the default, and it works the same as before. `WAREHOUSE=databricks` sends the same scripts to a Databricks SQL warehouse.

The rows stay in the warehouse on both platforms. Neo4j holds the document graph and the warehouse metadata, plus a few example values per column. The agent writes SQL for whichever warehouse is active.

The changes are on the `dbx-lakehouse` branch.

## How the Code Became Generic

- **One switch:** The `WAREHOUSE` value in `.env` picks the warehouse. Every script reads this one value.
- **A shared front door:** `warehouse.py` gives every script the same two functions, `query()` and `table()`. It loads only the chosen warehouse, so a BigQuery learner needs no Databricks settings.
- **Two back ends:** `bq.py` talks to BigQuery and did not change. The new `dbx.py` talks to Databricks. Both return rows in the same shape, a list of dictionaries.
- **One connections build:** `build_connections.py` runs the neocarta connector for the chosen warehouse. Both connectors build the same graph in Neo4j.
- **One playbook:** `SKILL.md` now says "the warehouse" instead of "BigQuery". It tells the agent to run `run_sql.py --info` before its first query, so the agent learns which SQL to write.
- **Matching descriptions:** The Databricks table and schema comments now copy the BigQuery text word for word. The agent sees the same descriptions on both warehouses.
- **Docs for both:** The README, `CLAUDE.md`, and the setup scripts now name both warehouses.

## Features

- **Warehouse switch:** Set `WAREHOUSE=databricks` in `.env` to use Databricks.
- **Databricks connections graph:** `build_connections.py` reads Unity Catalog metadata into Neo4j. The test build matched BigQuery: 6 tables, 24 columns, 5 join paths, and 204 example values.
- **Dialect check:** `run_sql.py --info` prints the warehouse, its SQL dialect, and how to write a table name.
- **Databricks SQL guidance:** `SKILL.md` lists the two SQL differences that matter. Databricks quotes each part of a table name separately. It counts true values with `count_if`, because `COUNTIF` fails there.
- **Path tool on both:** `path_query.py` turns two table names into a working SQL join, and it runs on BigQuery and Databricks.
  - **What you give it:** Two table names, such as `parts` and `vehicles`. You can add `--where` and `--select`.
  - **What it does:** It asks the connections graph in Neo4j which foreign keys link the two tables. It builds the `JOIN` SQL from that path. It runs the SQL on the active warehouse and prints the path, the SQL, and up to 20 rows.
  - **Why it works on both:** It calls `warehouse.py` to run the SQL and to quote table names. `warehouse.py` picks `bq.py` or `dbx.py` from `WAREHOUSE`. The graph has the same shape from either warehouse, so the path search is the same.
  - **Where it lives:** Only in `solutions/scripts/`. It is a finished demo. Learners do not build it.
  - **Example:** `python solutions/scripts/path_query.py parts vehicles --where "parts.part_number = 'IC-2042-B'"`
- **Catch-up copies:** `solutions/scripts/` holds a finished version of every tool in `skill/scripts/`. A learner who falls behind copies a file from `solutions/` into `skill/scripts/`.
  - **Same in both folders:** `warehouse.py`, `dbx.py`, `bq.py`, `db.py`, and `run_sql.py` are identical. Learners do not edit them. A learner on Databricks gets Databricks support either way.
  - **Different by design:** `outline.py`, `search.py`, and `themes.py` are unfinished in `skill/scripts/`. The learner fills in the `BUILD FROM SPEC` blocks. The copies in `solutions/scripts/` are complete.
  - **Extra file:** `path_query.py` exists only in `solutions/scripts/`.
- **Pinned neocarta:** `requirements.txt` installs neocarta from GitHub commit `ba6bf79`. No PyPI release has the Databricks connector yet.
- **One catalog default:** All three `databricks/` scripts default to the `lakehouse-workshop` catalog.
- **Instructor guide:** `databricks/README.md` lists the steps to load the data, grant read access, and hand out a token.
- **Read-only access:** The learner token can read the schema and nothing else. Tests showed every write attempt fails.
- **Query tag:** Every Databricks query carries the tag `neo4j-genai-workshop-lakehouse`. Search for it in the warehouse query history.

## What Changed

- **New files:** `warehouse.py` and `dbx.py`, in both `skill/scripts/` and `solutions/scripts/`.
- **Query scripts:** Both copies of `run_sql.py` now use `warehouse.py` and have `--info`. `path_query.py` uses `warehouse.py`.
- **Connections build:** `load/build_connections.py` has a new Databricks branch. Its BigQuery branch did not change.
- **Databricks loaders:** `load_databricks.py`, `upload_pdfs.py`, and `build_doc_index.py` default to `lakehouse-workshop`. `load_databricks.py` now reads the schema from `databricks/schema.sql`, which copies the BigQuery descriptions.
- **Setup:** `requirements.txt`, `.devcontainer/post-create.sh`, and `.devcontainer/post-create-local.sh`.
- **Instructor setup:** `.env.example` has a Databricks section that lists every variable. `databricks/env_set.sh` updates one `.env` line and keeps the rest. `databricks/schema.sql` holds the Databricks schema, the twin of `bigquery/schema.sql`. `databricks/setup_readonly_access.sh` creates the read-only service principal, grants, warehouse access, and token.
- **Docs:** `README.md`, `CLAUDE.md`, `SKILL.md`, `databricks/README.md`, and one comment in `load/load_documents.py`.

## Run and Test

Run every block from the repo root in one terminal. Values in angle brackets, like `<workspace-host>`, are placeholders. Replace them with your own workspace values. Keep real values out of this file.

The instructor steps live in [`databricks/README.md`](databricks/README.md). This file points to them and adds the test steps.

### Step 1: Install

```bash
cd ~/projects/workshops/genai-workshop-lakehouse
source .venv/bin/activate
pip install -r requirements.txt
python -c "from neocarta.connectors.databricks import DatabricksSchemaConnector; print('ok')"
```

Expect `ok`.

### Step 2: Check that BigQuery still works

```bash
python skill/scripts/run_sql.py --info
python skill/scripts/run_sql.py 'SELECT model, COUNT(*) AS n FROM `neo4jeventdemos.autofix_service.vehicles` GROUP BY model'
python solutions/scripts/path_query.py parts vehicles \
  --where "parts.part_number = 'IC-2042-B'" \
  --select "DISTINCT vehicles.vin, vehicles.model, work_orders.wo_id"
```

Expect these results:

- **Info:** The first command prints `warehouse: bigquery`.
- **Query:** The second prints a count per model.
- **Path:** The third prints `PATH : parts -> work_order_parts -> work_orders -> vehicles` and 20 rows. It needs a connections graph in Neo4j, from either warehouse.

### Step 3: Run the instructor setup

Follow Steps 2 to 5 of [`databricks/README.md`](databricks/README.md) in this terminal. They do these jobs:

- **Workspace values:** Set the Databricks section of `.env`, including `WAREHOUSE=databricks`, then load it into the shell. Scripts and shell then use the same values.
- **Data:** Create the catalog and load the six tables.
- **Access:** `setup_readonly_access.sh` creates the read-only service principal, grants it read access on the schema, and lets it use the warehouse.
- **Token:** The same script creates the token that learners use.

For this test, run Step 5 with `--lifetime 3600`. The token then lasts 1 hour. After Step 5, add this `trap`. It revokes the token when the shell exits:

```bash
trap './databricks/setup_readonly_access.sh --revoke' EXIT
```

### Step 4: Build the connections graph from Databricks

Step 6 of the instructor guide runs the same build. Run it here too if you skipped that step.

```bash
python load/build_connections.py
```

Expect `Connections graph ready: 6 tables, 5 REFERENCES (join paths).` Fewer than 5 means a grant is missing.

### Step 5: Run SQL on Databricks

```bash
python skill/scripts/run_sql.py --info
python skill/scripts/run_sql.py "SELECT count(DISTINCT w.wo_id) AS work_orders, count_if(w.comeback) AS comebacks
  FROM \`lakehouse-workshop\`.\`autofix_service\`.\`work_orders\` w
  JOIN \`lakehouse-workshop\`.\`autofix_service\`.\`vehicles\` v ON w.vin = v.vin
  WHERE v.model = 'Falcon' AND v.engine = '2.0T' AND w.dtc_code = 'P0301'"
python solutions/scripts/path_query.py parts vehicles \
  --where "parts.part_number = 'IC-2042-B'" \
  --select "DISTINCT vehicles.vin, vehicles.model, work_orders.wo_id"
```

Expect these results:

- **Info:** The first command prints `warehouse: databricks` and the table form `` `lakehouse-workshop`.`autofix_service`.`<table>` ``.
- **Counts:** The second prints 29 work orders and 6 comebacks. BigQuery gives the same numbers.
- **Path:** The third prints the same path as on BigQuery and 20 rows.

### Step 6: Test the agent on the warehouse

Do not tell the agent which warehouse it is on. The test checks that `SKILL.md` and `--info` lead it to the right SQL.

Headless `claude -p` needs the `--model` flag when Claude Code runs through the Databricks gateway. Without it, the gateway rejects the default model name with a 403. The gateway setup defines `ANTHROPIC_DEFAULT_SONNET_MODEL`. The commands below add `--model` only when that variable is set, so they also work without the gateway.

```bash
claude mcp list   # expect: connections ... Connected
MODEL_ARGS=()
[ -n "$ANTHROPIC_DEFAULT_SONNET_MODEL" ] && MODEL_ARGS=(--model "$ANTHROPIC_DEFAULT_SONNET_MODEL")
ALLOWED='Skill,Read,mcp__connections__*,Bash(python skill/scripts/run_sql.py:*),Bash(python skill/scripts/search.py:*),Bash(python skill/scripts/outline.py:*)'
Q1='Using the autofix-service-advisor skill: on Falcon vehicles with the 2.0T engine, how many work orders were diagnosed with P0301, and how many of those were comebacks?'
Q2='Using the autofix-service-advisor skill: for Falcon 2.0T work orders diagnosed with P0301, which parts were replaced, how many work orders used each, and how many comebacks did each have?'
claude -p "$Q1" "${MODEL_ARGS[@]}" --allowedTools "$ALLOWED" \
  --output-format stream-json --verbose --max-turns 30 < /dev/null > /tmp/agent_q1.jsonl
claude -p "$Q2" "${MODEL_ARGS[@]}" --allowedTools "$ALLOWED" \
  --output-format stream-json --verbose --max-turns 30 < /dev/null > /tmp/agent_q2.jsonl
```

Show what the agent ran and what it answered:

```bash
for i in 1 2; do
  echo "== Q$i commands"
  jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name + "  " + ((.input.command // (.input|tostring)) | .[0:300])' /tmp/agent_q$i.jsonl
  echo "== Q$i answer"
  jq -r 'select(.type=="result") | .result' /tmp/agent_q$i.jsonl
done
grep -c dapi /tmp/agent_q1.jsonl /tmp/agent_q2.jsonl   # expect 0 and 0: no token in the transcripts
```

The test passes when all of these are true for both questions:

- **Info first:** The agent ran `run_sql.py --info` before its first SQL.
- **Table form:** Each part of every table name has its own backticks.
- **Counting:** The agent used `count_if(comeback)` and never ran a failed `COUNTIF`.
- **Joins:** The agent took its joins from the `connections` MCP.

The numbers must match BigQuery:

- **Q1:** 29 work orders and 6 comebacks.
- **Q2:** SP-1108 Spark plug set, 29 used and 6 comebacks. IC-2042-B Ignition coil (revised), 18 used and 0 comebacks. IC-2042-A Ignition coil (original), 11 used and 6 comebacks.

### Step 7: Load the documents and ask the full question

This step writes the document graph to the Neo4j instance in `.env`. The connections graph stays.

```bash
python load/load_documents.py
python skill/scripts/search.py "P0301"   # expect hits with section URIs
ALLOWED_B="$ALLOWED,Bash(python skill/scripts/themes.py:*),Bash(neo4j-cli:*)"
Q3='Using the autofix-service-advisor skill: what fixed P0301 on vehicles like FAL20T20190053?'
claude -p "$Q3" "${MODEL_ARGS[@]}" --allowedTools "$ALLOWED_B" \
  --output-format stream-json --verbose --max-turns 40 < /dev/null > /tmp/agent_q3.jsonl
jq -r 'select(.type=="result") | .result' /tmp/agent_q3.jsonl
grep -c dapi /tmp/agent_q3.jsonl   # expect 0
```

The answer passes when all of these are true:

- **Grounding:** It cites document section URIs found by search.
- **Vehicle:** It reads FAL20T20190053 as a Falcon 2.0T from the warehouse.
- **Ranking:** It ranks IC-2042-B first, with 18 uses and 0 comebacks.

### Step 8: Clean up

```bash
exit   # the trap revokes the token and clears it from .env; the count it prints should be 0
```

To go back to BigQuery, set `WAREHOUSE=bigquery` in `.env`. Open a new terminal, or run `set -a; source .env; set +a`.

## Architecture

### The Big Picture

![Architecture: two halves, one agent](dbx-summary-diagrams/architecture.svg)

- **Documents:** `load_documents.py` parses the PDFs into a document graph in Neo4j.
- **Warehouse metadata:** `build_connections.py` copies the table and column metadata into a connections graph. It also copies a few example values per column. It never copies the rows.
- **Agent:** Claude Code reads both graphs, then runs live SQL on the warehouse for the facts.

### The Warehouse Switch

![One switch picks the warehouse](dbx-summary-diagrams/warehouse-switch.svg)

- **Query time:** `run_sql.py` and `path_query.py` call `warehouse.py`. It hands the SQL to `bq.py` or `dbx.py`, based on `WAREHOUSE`.
- **Build time:** `build_connections.py` picks the matching neocarta connector. Both connectors produce the same graph, so the agent's tools work the same on both.

### One Question, Start to Finish

![How the agent answers one question](dbx-summary-diagrams/question-flow.svg)

- **Neo4j steps:** The agent searches the documents for the trouble code. The matching sections name the parts. The connections graph gives the join paths.
- **Warehouse steps:** `--info` tells the agent which SQL to write. The SQL counts how often each part was used and how often the vehicle came back.
- **The link:** Part numbers appear in both the documents and the warehouse. That shared key joins the two halves.

## Known Limits and Open Items

- **BigQuery build check:** The BigQuery connections build has not run at the new neocarta pin. This blocks the merge.
- **Host and path:** `.env.example` gets the Databricks host and HTTP path once the live workspace is chosen. The test workspace values stay out of the repo.
- **Agent tests:** Steps 6 and 7 have not passed yet. Step 6 decides whether the course can merge its two warehouse tabs into one note.
- **Load test:** Nobody has tested many learners on one SQL warehouse. Size the warehouse for the class.
- **Shared Neo4j:** `path_query.py` reads join paths from every database in Neo4j. Build only one warehouse into each Neo4j instance.
- **GCP_PROJECT_ID:** `build_connections.py` still needs it set on Databricks, because it reads it on start. `.env.example` sets it.
- **Code review:** zooz's review found no high-severity issues. Seven findings are fixed. The host and path wording waits on the live workspace, and the install time check waits for Phase 6. The zooz code review table is in the maintainer's local `add-dbx.md`. Git excludes that file.

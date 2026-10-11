# AI on Your Lakehouse — workshop environment

Companion environment for the GraphAcademy workshop
**AI on Your Lakehouse: Context Comes in Shapes, Not Queries**.

You build a **service-advisor skill** for AutoFix Group: a playbook + scripts that
let your coding agent answer questions about the technical library and the repair
history — grounded in a graph that spans the lakehouse's documents and warehouse
tables.

The data comes in two halves that share keys (part numbers, trouble codes):

- **Documents** — repair manuals, service bulletins, and recall notices (PDFs),
  parsed into a Neo4j **document graph** (a navigable tree plus Leiden themes).
- **Warehouse** — vehicles, work orders, and parts in **BigQuery** by default, or
  in **Databricks**. The rows stay in the warehouse. **neocarta** reads their
  metadata plus a few example values per column into a Neo4j **connections**
  graph. The metadata includes the foreign-key join paths, and the agent
  federates across the two halves.

## Quick start

### In a Codespace (recommended)

Open the repo in a GitHub Codespace — `.devcontainer/post-create.sh` installs
everything for you: Python dependencies, the Neo4j CLI with its agent skills, and
Claude Code.

→ [Open in GitHub Codespace](https://github.com/codespaces/new/zach-blumenfeld/genai-workshop-lakehouse)

### Locally

```bash
git clone https://github.com/zach-blumenfeld/genai-workshop-lakehouse
cd genai-workshop-lakehouse
./.devcontainer/post-create-local.sh   # isolated venv + deps + neo4j-cli + agent skills
source .venv/bin/activate
```

Then add your credentials to `.env` (the setup script copies it from
`.env.example`):

- **Neo4j** — a sandbox with the Graph Data Science library (a
  [GDS blank sandbox](https://sandbox.neo4j.com) works). Paste `NEO4J_URI`,
  `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`.
- **BigQuery** — the workshop dataset is read-only; use the one-line
  `BIGQUERY_SA_KEY_B64` from the workshop, or use your own `gcloud` login. To
  provision your own copy of the warehouse, see [`bigquery/`](bigquery/).
- **Databricks** — to use Databricks instead of BigQuery, set
  `WAREHOUSE=databricks` and fill in `DATABRICKS_SERVER_HOSTNAME`,
  `DATABRICKS_HTTP_PATH`, and `DATABRICKS_TOKEN`. Your instructor provides these
  values, including a read-only token. Never commit the token. Keep
  `GCP_PROJECT_ID` set, because `load/build_connections.py` reads it on start.
  To provision the warehouse yourself, see
  [`databricks/`](databricks/README.md#part-1-the-main-path-warehousedatabricks).
- **Anthropic** — set `ANTHROPIC_API_KEY`, or leave it blank to use your Claude
  Code subscription.

## Set up your coding agent

The workshop uses Claude Code as the coding agent. It needs three things:

- **Claude Code:** The agent itself.
- **The `connections` MCP server:** It lets the agent read the warehouse map from Neo4j. The repo defines it in `.mcp.json`, and `run-mcp.sh` starts it.
- **The skill:** `skill/SKILL.md` is the agent's playbook. It is already in the repo.

### In a Codespace

The setup runs for you. `.devcontainer/post-create.sh` does this when the Codespace starts:

- **Claude Code:** It installs Claude Code.
- **Python packages:** It installs `requirements.txt`. This includes `neocarta-mcp`, the program behind the `connections` server.
- **Neo4j CLI and skills:** It installs `neo4j-cli`, `neo4j-cypher-skill`, and `neo4j-gds-skill`. The agent uses them in steps 3 and 4 of the workshop flow.
- **Environment file:** It copies `.env.example` to `.env`. It also loads `.env` into every new terminal.

You add your Neo4j values to `.env`, run step 1 of the workshop flow, and start the agent with `claude` in a second terminal. Approve the `connections` server when Claude Code asks.

### On your laptop

The setup script does not install Claude Code on a laptop, so you do these steps yourself:

1. **Install Claude Code:**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```
2. **Run the setup script** from the Quick start above, if you have not already. It makes `.venv`, installs `requirements.txt` with `neocarta-mcp`, installs the Neo4j CLI and its skills, and creates `.env`.
3. **Fill in `.env`.** Add `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`. The `connections` server reads them from this file.
4. **Build the connections graph.** Run step 1 of the workshop flow below. The server has nothing to serve until this graph exists.
5. **Start the agent** from the repo root:
   ```bash
   claude
   ```
6. **Approve the `connections` server.** Claude Code asks the first time it sees `.mcp.json`. Run `/mcp` to check. `connections` should show as connected.
7. **Fix a failed connection.** If `/mcp` shows `connections` as failed, check the Neo4j values in `.env`. Then reconnect from the `/mcp` menu.

## The workshop flow

The workshop has five steps. The GraphAcademy course walks through each one. Here is
what each step does and the command to run.

In short, you give your coding agent three tools for the library and one map of the
warehouse. At the end, the agent combines them to answer real questions.

1. **Connections (Module 2):** Build a map of the warehouse.
   ```bash
   python load/build_connections.py
   ```
   - **What it does:** It reads the warehouse's table names, column names, a few example values, and the foreign keys. It writes them to Neo4j as the **connections graph**.
   - **What it does not do:** It does not copy any rows. The data stays in the warehouse.
   - **Why it matters:** The foreign keys show how the tables join. The agent uses them to write correct SQL.
   - **Try it:** Approve the `connections` MCP in your agent. Ask a warehouse question. Watch the agent read the map and write SQL. Run SQL yourself with `python skill/scripts/run_sql.py "<SQL>"`.

2. **Trees (Module 3), load the documents:** Put the PDFs into Neo4j.
   ```bash
   python load/load_documents.py
   ```
   - **What it does:** It reads the manuals, service bulletins, and recall notices. It builds one **document graph** from them.
   - **Tree:** Each PDF becomes Library, Folder, Document, then Section. This works like a table of contents.
   - **Links:** A reference from one document to another becomes a `LINKS_TO` edge.
   - **Search index:** All the section text goes into one full-text index.

3. **Trees (Module 3), build the tools:** Ask your coding agent to write the library tools.
   - **What to ask:** Tell your agent: "Fill the `BUILD FROM SPEC` blocks in `skill/scripts/outline.py` and `skill/scripts/search.py`. Follow `docs/outline-format.md`."
   - **What the agent does:** It writes the Cypher queries that are missing from those two files. The spec says what each query must return.
   - **`outline.py`:** It shows the whole library as a table of contents.
   - **`search.py`:** It searches the section text.
   - **Run them:**
     ```bash
     python skill/scripts/outline.py
     python skill/scripts/search.py "<query>"
     ```

4. **Themes (Module 4):** Ask your coding agent to group the documents.
   - **What to ask:** Tell your agent: "Fill the `BUILD FROM SPEC` block in `skill/scripts/themes.py`. Follow `docs/theme-format.md`."
   - **What the script does:** It runs Leiden community detection on the `LINKS_TO` edges. Documents that reference each other land in the same **theme**.
   - **Run it:**
     ```bash
     python skill/scripts/themes.py
     ```
   - **`--gamma`:** This sets the theme size. A higher value gives more, smaller themes. A lower value gives fewer, larger themes.
   - **Requirement:** Themes need the Neo4j Graph Data Science library. A GDS sandbox has it.

5. **Finale (Module 6):** Ask real questions. The agent combines the tools.
   - **What to do:** Start your agent in the repo root. It reads `skill/SKILL.md` as its playbook.
   - **What the agent does:** It picks the tool that fits each question. It reads documents with the outline, search, and themes. It reads the warehouse with SQL.
   - **Example questions:**
     - *"For VIN FAL20T20220002 with code P0301: what fixed this on similar vehicles?"*
     - *"What are the common patterns across all our bulletins and recalls?"*
     - *"Which fault codes are failing in the field but have no documentation?"*

If you get stuck, `solutions/scripts/` has every finished tool.

## Layout

| Path | What |
|---|---|
| `corpus/` | The document half as authored markdown (`<area>/<id>.md`), the source of truth |
| `sources/pdfs/` | The corpus rendered to PDFs (manuals, bulletins, recalls) — what the loader parses |
| `sources/warehouse/` | CSV exports of the warehouse tables `autofix.service.*`, which load both BigQuery and Databricks |
| `load/` | The pipelines: `build_connections.py` (warehouse metadata graph) and `load_documents.py` (document graph) |
| `skill/` | **What you build** — the service-advisor skill: `SKILL.md` playbook + `scripts/` tools |
| `solutions/` | Complete scripts — catch up or compare |
| `docs/` | The shape specs (`outline-format.md`, `theme-format.md`) you build against |
| `bigquery/` | Provision your own copy of the AutoFix warehouse in BigQuery |
| `databricks/` | Provision the AutoFix warehouse in Databricks, plus an optional Genie + AI Search path |
| `tools/` | Authoring tools: `render_corpus.py` (markdown → PDFs), `generate_warehouse.py` (warehouse CSVs) |

## Running it locally

The loaders are idempotent, but to wipe the graph and start clean:

```bash
neo4j-cli query --uri "$NEO4J_URI" --username "$NEO4J_USERNAME" --password "$NEO4J_PASSWORD" \
  "MATCH (n) DETACH DELETE n" --rw
neo4j-cli query --uri "$NEO4J_URI" --username "$NEO4J_USERNAME" --password "$NEO4J_PASSWORD" \
  "DROP INDEX content_search IF EXISTS" --rw
```

If a themes run crashes, run it again. It cleans up its own projection first.

## Swapping in a real lakehouse

The pattern is source-agnostic:

- **Warehouse** — point neocarta at your own warehouse (declared keys → the same
  connections graph). The rows stay put; the agent federates with live SQL. Or
  stand the data up on **Databricks** (Genie + AI Search) — see [`databricks/`](databricks/).
- **Documents** — point `load/parse_corpus.py:iter_pdf_paths()` at your storage
  (`PDF_SOURCE=gcs` reads the same folder layout from a bucket).
- Everything downstream — graph model, skill, and tools — is unchanged.

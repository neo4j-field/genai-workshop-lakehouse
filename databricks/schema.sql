-- AutoFix warehouse - Databricks DDL with PRIMARY KEY / FOREIGN KEY constraints.
--
-- This is the Databricks twin of bigquery/schema.sql. It has the same tables, the
-- same columns, the same table descriptions, and the same foreign key names.
-- Only the dialect differs:
--   BigQuery STRING / INT64 / FLOAT64 / BOOL   ->  Databricks STRING / INT / DOUBLE / BOOLEAN
--   OPTIONS (description = '...')              ->  COMMENT '...'
--   PRIMARY KEY (...) NOT ENFORCED             ->  CONSTRAINT <name> PRIMARY KEY (...)
--   ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS ... FOREIGN KEY
--                                              ->  CONSTRAINT <name> FOREIGN KEY inside CREATE TABLE
--
-- Databricks does not enforce these constraints. Unity Catalog lists them in
-- information_schema, and neocarta reads them to build the Column-[:REFERENCES]->Column
-- graph (the connections shape). Without declared keys, the graph has no join paths.
--
-- Placeholders ${CATALOG} and ${SCHEMA} are filled by load_databricks.py.
-- Run order matters: a table must exist before another table points a foreign key at it.
-- Every statement ends with a semicolon. load_databricks.py runs them one at a time.

CREATE SCHEMA IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`
  COMMENT 'AutoFix Group service warehouse (workshop sample)';

CREATE TABLE IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`.`vehicles` (
  vin STRING NOT NULL,
  make STRING,
  model STRING,
  year INT,
  engine STRING,
  CONSTRAINT pk_vehicles PRIMARY KEY (vin)
) COMMENT 'One row per serviced vehicle.';

CREATE TABLE IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`.`dtc_codes` (
  code STRING NOT NULL,
  description STRING,
  CONSTRAINT pk_dtc_codes PRIMARY KEY (code)
) COMMENT 'Diagnostic trouble code reference (OBD-II).';

CREATE TABLE IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`.`procedures` (
  procedure_id STRING NOT NULL,
  name STRING,
  labor_hours DOUBLE,
  CONSTRAINT pk_procedures PRIMARY KEY (procedure_id)
) COMMENT 'Labor procedures performed on work orders.';

CREATE TABLE IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`.`parts` (
  part_number STRING NOT NULL,
  name STRING,
  superseded_by STRING,
  CONSTRAINT pk_parts PRIMARY KEY (part_number)
) COMMENT 'Parts catalog; superseded_by points to the replacement part.';

-- Foreign keys = the join paths neocarta turns into REFERENCES edges.
-- parts.superseded_by points back at parts. It stays a plain column, as in BigQuery.
-- The agent reads supersession with SQL.

CREATE TABLE IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`.`work_orders` (
  wo_id STRING NOT NULL,
  vin STRING,
  opened DATE,
  odometer INT,
  complaint STRING,
  dtc_code STRING,
  procedure_id STRING,
  comeback BOOLEAN,
  CONSTRAINT pk_work_orders PRIMARY KEY (wo_id),
  CONSTRAINT fk_wo_vehicle FOREIGN KEY (vin) REFERENCES `${CATALOG}`.`${SCHEMA}`.`vehicles`(vin),
  CONSTRAINT fk_wo_dtc FOREIGN KEY (dtc_code) REFERENCES `${CATALOG}`.`${SCHEMA}`.`dtc_codes`(code),
  CONSTRAINT fk_wo_procedure FOREIGN KEY (procedure_id) REFERENCES `${CATALOG}`.`${SCHEMA}`.`procedures`(procedure_id)
) COMMENT 'A repair visit; comeback = true means the vehicle returned with the same problem.';

CREATE TABLE IF NOT EXISTS `${CATALOG}`.`${SCHEMA}`.`work_order_parts` (
  wo_id STRING NOT NULL,
  part_number STRING NOT NULL,
  qty INT,
  CONSTRAINT pk_work_order_parts PRIMARY KEY (wo_id, part_number),
  CONSTRAINT fk_wop_workorder FOREIGN KEY (wo_id) REFERENCES `${CATALOG}`.`${SCHEMA}`.`work_orders`(wo_id),
  CONSTRAINT fk_wop_part FOREIGN KEY (part_number) REFERENCES `${CATALOG}`.`${SCHEMA}`.`parts`(part_number)
) COMMENT 'Parts replaced on a work order (bridge: work_orders <-> parts).';

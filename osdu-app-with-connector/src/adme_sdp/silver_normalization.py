# Databricks notebook source
# MAGIC %pip install -q 'httpx>=0.27' 'azure-identity>=1.15' 'pydantic>=2.5' 'PyYAML>=6' 'tenacity>=8'

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC # Silver Normalization — ADME OSDU Lakeflow SDP
# MAGIC
# MAGIC Reads Bronze tables, normalizes OSDU records, and deduplicates
# MAGIC via SCD Type 1 (latest `modify_time` wins per `record_id`).

# COMMAND ----------

import json
import os
import sys
from pathlib import Path

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.functions import col
from pyspark.sql.window import Window

# --- Bootstrap connector package path ---
_nb_dir = Path(os.path.dirname(os.path.abspath(__file__))) if "__file__" in dir() else Path.cwd()
_candidates = [_nb_dir.parent, _nb_dir.parent / "files", _nb_dir.parent.parent, _nb_dir.parent.parent / "files"]
for _c in _candidates:
    if (_c / "connector" / "__init__.py").is_file():
        if str(_c) not in sys.path:
            sys.path.insert(0, str(_c))
        break

from connector.domains.registry import load_domains_from_dir
from connector.models.config import DomainConfig

# COMMAND ----------

def _load_domains() -> dict[str, DomainConfig]:
    for _c in _candidates:
        d = _c / "conf" / "domains"
        if d.is_dir():
            return load_domains_from_dir(d)
    return {}


_DOMAINS = _load_domains()

# COMMAND ----------

def _build_silver_query(domain_name: str):
    """Build the silver DataFrame from a bronze table with normalization and dedup."""
    bronze_table = f"bronze_{domain_name}"
    domain = _DOMAINS[domain_name]
    norm = domain.normalization

    df = spark.read.table(bronze_table)

    silver_df = df.select(
        col("bronze_id"),
        col("domain"),
        F.get_json_object(col("raw_json"), f"$.{norm.record_id_path}").alias("record_id"),
        F.get_json_object(col("raw_json"), f"$.{norm.record_kind_path}").alias("kind"),
        F.get_json_object(col("raw_json"), f"$.{norm.modify_time_path}").alias("modify_time"),
        col("raw_json").alias("silver_payload"),
        col("ingestion_ts").alias("ingested_at"),
    )

    for silver_col, path in norm.field_map.items():
        json_path = "$." + path
        silver_df = silver_df.withColumn(silver_col, F.get_json_object(col("silver_payload"), json_path))

    # Deduplicate: keep latest modify_time per record_id (SCD Type 1)
    w = Window.partitionBy("record_id").orderBy(F.desc("modify_time"), F.desc("ingested_at"))
    silver_df = silver_df.withColumn("_rn", F.row_number().over(w)).filter(col("_rn") == 1).drop("_rn")

    return silver_df

# COMMAND ----------

@dp.table(
    name="silver_wellbore",
    comment="Normalized and deduplicated wellbore records (latest modify_time per record_id).",
    cluster_by=["record_id"],
)
def silver_wellbore():
    return _build_silver_query("wellbore")


@dp.table(
    name="silver_reservoir",
    comment="Normalized and deduplicated reservoir records (latest modify_time per record_id).",
    cluster_by=["record_id"],
)
def silver_reservoir():
    return _build_silver_query("reservoir")


@dp.table(
    name="silver_rock_and_fluid",
    comment="Normalized and deduplicated rock & fluid records (latest modify_time per record_id).",
    cluster_by=["record_id"],
)
def silver_rock_and_fluid():
    return _build_silver_query("rock_and_fluid")

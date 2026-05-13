# Databricks notebook source
# MAGIC %md
# MAGIC # Gold Views — ADME OSDU Lakeflow SDP
# MAGIC
# MAGIC Materialized views optimized for consumption: dashboards, Genie Spaces,
# MAGIC and downstream analytics. Reads from Silver tables.

# COMMAND ----------

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.functions import col

# COMMAND ----------

@dp.materialized_view(
    name="gold_domain_summary",
    comment="Record counts and latest modification timestamps per domain.",
)
def gold_domain_summary():
    from functools import reduce
    from pyspark.sql import DataFrame

    dfs = []
    for domain in ["wellbore", "reservoir", "rock_and_fluid"]:
        table_name = f"silver_{domain}"
        df = (
            spark.read.table(table_name)
            .groupBy("domain")
            .agg(
                F.count("*").alias("record_count"),
                F.max("modify_time").alias("latest_modify_time"),
                F.max("ingested_at").alias("latest_ingested_at"),
                F.countDistinct("kind").alias("distinct_kinds"),
            )
        )
        dfs.append(df)

    return reduce(DataFrame.unionAll, dfs)


@dp.materialized_view(
    name="gold_wellbore_catalog",
    comment="Curated wellbore catalog with key business fields extracted from silver.",
)
def gold_wellbore_catalog():
    return (
        spark.read.table("silver_wellbore")
        .select(
            col("record_id"),
            col("kind"),
            col("modify_time"),
            F.get_json_object(col("silver_payload"), "$.data.FacilityName").alias("facility_name"),
            F.get_json_object(col("silver_payload"), "$.data.CountryID").alias("country"),
            F.get_json_object(col("silver_payload"), "$.data.TotalDepth").cast("double").alias("total_depth"),
            F.get_json_object(col("silver_payload"), "$.data.WaterDepth").cast("double").alias("water_depth"),
            F.get_json_object(col("silver_payload"), "$.data.Elevation").cast("double").alias("elevation"),
            F.get_json_object(col("silver_payload"), "$.data.WellboreTrajectoryTypeID").alias("trajectory_type"),
            col("ingested_at"),
        )
    )


@dp.materialized_view(
    name="gold_reservoir_catalog",
    comment="Curated reservoir catalog with key subsurface fields.",
)
def gold_reservoir_catalog():
    return (
        spark.read.table("silver_reservoir")
        .select(
            col("record_id"),
            col("kind"),
            col("modify_time"),
            F.get_json_object(col("silver_payload"), "$.data.FacilityName").alias("facility_name"),
            F.get_json_object(col("silver_payload"), "$.data.ReservoirName").alias("reservoir_name"),
            F.get_json_object(col("silver_payload"), "$.data.GrossThickness").cast("double").alias("gross_thickness"),
            F.get_json_object(col("silver_payload"), "$.data.NetPayThickness").cast("double").alias("net_pay_thickness"),
            F.get_json_object(col("silver_payload"), "$.data.Porosity").cast("double").alias("porosity"),
            F.get_json_object(col("silver_payload"), "$.data.Permeability").cast("double").alias("permeability"),
            col("ingested_at"),
        )
    )


@dp.materialized_view(
    name="gold_rock_and_fluid_catalog",
    comment="Curated rock & fluid sample catalog.",
)
def gold_rock_and_fluid_catalog():
    return (
        spark.read.table("silver_rock_and_fluid")
        .select(
            col("record_id"),
            col("kind"),
            col("modify_time"),
            F.get_json_object(col("silver_payload"), "$.data.SampleType").alias("sample_type"),
            F.get_json_object(col("silver_payload"), "$.data.SampleID").alias("sample_id"),
            F.get_json_object(col("silver_payload"), "$.data.Lithology").alias("lithology"),
            F.get_json_object(col("silver_payload"), "$.data.FluidType").alias("fluid_type"),
            F.get_json_object(col("silver_payload"), "$.data.Density").cast("double").alias("density"),
            col("ingested_at"),
        )
    )

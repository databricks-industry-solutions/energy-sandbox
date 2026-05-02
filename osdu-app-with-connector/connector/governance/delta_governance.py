"""Create and overwrite governance mirror Delta tables in Unity Catalog."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from connector.models.config import ConnectorRuntimeConfig
from connector.utils.uc_catalog import ensure_catalog_schema_for_delta

logger = logging.getLogger(__name__)


def ensure_governance_schema(spark: Any, runtime: ConnectorRuntimeConfig) -> None:
    ensure_catalog_schema_for_delta(spark, runtime.delta.catalog, runtime.delta.schema_name)


def write_legal_tags(spark: Any, runtime: ConnectorRuntimeConfig, rows: Iterable[dict]) -> int:
    from pyspark.sql import Row
    from pyspark.sql.types import (
        BooleanType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    rlist = list(rows)
    if not rlist:
        return 0
    schema = StructType(
        [
            StructField("legal_tag_name", StringType(), False),
            StructField("legal_tag_id", StringType(), False),
            StructField("is_valid", BooleanType(), False),
            StructField("data_partition_id", StringType(), False),
            StructField("obligations_json", StringType(), True),
            StructField("raw_json", StringType(), False),
            StructField("ingested_at", TimestampType(), False),
            StructField("source", StringType(), False),
        ]
    )
    pyrows = [Row(**{k: x[k] for k in schema.fieldNames()}) for x in rlist]
    df = spark.createDataFrame(pyrows, schema)
    fqn = runtime.delta.legal_tags_fqn()
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(fqn)
    logger.info("Wrote %s rows to %s", len(rlist), fqn)
    return len(rlist)


def write_entitlements_groups(spark: Any, runtime: ConnectorRuntimeConfig, rows: Iterable[dict]) -> int:
    from pyspark.sql import Row
    from pyspark.sql.types import StringType, StructField, StructType, TimestampType

    rlist = list(rows)
    if not rlist:
        return 0
    schema = StructType(
        [
            StructField("group_id", StringType(), False),
            StructField("group_name", StringType(), False),
            StructField("description", StringType(), False),
            StructField("data_partition_id", StringType(), False),
            StructField("raw_json", StringType(), False),
            StructField("ingested_at", TimestampType(), False),
            StructField("source", StringType(), False),
        ]
    )
    pyrows = [Row(**{k: x[k] for k in schema.fieldNames()}) for x in rlist]
    df = spark.createDataFrame(pyrows, schema)
    fqn = runtime.delta.entitlements_fqn()
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(fqn)
    logger.info("Wrote %s rows to %s", len(rlist), fqn)
    return len(rlist)


def write_record_acl_mirror(spark: Any, runtime: ConnectorRuntimeConfig, rows: Iterable[dict]) -> int:
    from pyspark.sql import Row
    from pyspark.sql.types import StringType, StructField, StructType, TimestampType

    rlist = list(rows)
    if not rlist:
        return 0
    schema = StructType(
        [
            StructField("object_id", StringType(), False),
            StructField("resource_type", StringType(), False),
            StructField("principal_id", StringType(), False),
            StructField("privilege", StringType(), False),
            StructField("data_partition_id", StringType(), False),
            StructField("raw_json", StringType(), False),
            StructField("ingested_at", TimestampType(), False),
            StructField("source", StringType(), False),
        ]
    )
    pyrows = [Row(**{k: x[k] for k in schema.fieldNames()}) for x in rlist]
    df = spark.createDataFrame(pyrows, schema)
    fqn = runtime.delta.record_acl_mirror_fqn()
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(fqn)
    logger.info("Wrote %s rows to %s", len(rlist), fqn)
    return len(rlist)

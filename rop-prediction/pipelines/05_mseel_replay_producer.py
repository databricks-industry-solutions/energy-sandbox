"""
05_mseel_replay_producer.py
────────────────────────────
Reads drilling_demo_bronze.mseel_drilling_raw for a chosen well and publishes
each record as a JSON event to a Kafka / Zerobus topic, simulating live
drilling data at configurable playback speed.

Can run as a Databricks Job or standalone Python script.

Usage:
    python 05_mseel_replay_producer.py \
        --well MIP_3H \
        --speed 0.5 \
        --topic drilling_mseel_stream \
        --bootstrap broker:9092

Environment variable overrides:
    REPLAY_WELL       : well_id to replay (default MIP_3H)
    REPLAY_SPEED      : seconds between records (default 0.5)
    KAFKA_BOOTSTRAP   : Kafka broker(s) (default localhost:9092)
    KAFKA_TOPIC       : topic name (default drilling_mseel_stream)
    REPLAY_MAX_ROWS   : max rows to replay per run (0 = all)
    REPLAY_LOOP       : if 1, loop back to start when exhausted
"""

import argparse
import json
import math
import os
import time
from datetime import timezone

# ── Configuration ─────────────────────────────────────────────
REPLAY_WELL     = os.getenv("REPLAY_WELL",     "MIP_3H")
REPLAY_SPEED    = float(os.getenv("REPLAY_SPEED", "0.5"))      # seconds per record
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC     = os.getenv("KAFKA_TOPIC",     "drilling_mseel_stream")
REPLAY_MAX_ROWS = int(os.getenv("REPLAY_MAX_ROWS", "0"))        # 0 = unlimited
REPLAY_LOOP     = os.getenv("REPLAY_LOOP", "0") == "1"


def parse_args():
    p = argparse.ArgumentParser(description="MSEEL Drilling Replay Producer")
    p.add_argument("--well",      default=REPLAY_WELL,      help="Well ID to replay (default: MIP_3H)")
    p.add_argument("--speed",     default=REPLAY_SPEED,     type=float, help="Seconds per record (default: 0.5)")
    p.add_argument("--topic",     default=KAFKA_TOPIC,      help="Kafka/Zerobus topic name")
    p.add_argument("--bootstrap", default=KAFKA_BOOTSTRAP,  help="Kafka bootstrap servers")
    p.add_argument("--max-rows",  default=REPLAY_MAX_ROWS,  type=int,   help="Max rows to publish (0 = all)")
    p.add_argument("--loop",      action="store_true",      default=REPLAY_LOOP, help="Loop replay")
    return p.parse_args()


def _make_producer(bootstrap_servers: str):
    """Create a kafka-python Producer, falling back to a no-op stub."""
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks=1,
            retries=3,
            linger_ms=5,            # small batching window
            batch_size=16_384,
        )
        print(f"  ✓ Connected to Kafka: {bootstrap_servers}")
        return producer
    except ImportError:
        print("  ⚠ kafka-python not installed — using stdout stub producer")
        return _StdoutProducer()
    except Exception as e:
        print(f"  ⚠ Kafka unavailable ({e}) — using stdout stub producer")
        return _StdoutProducer()


class _StdoutProducer:
    """No-op producer for local testing without a Kafka broker."""
    def send(self, topic, value):
        print(f"  [STUB] → {topic}: {json.dumps(value)[:120]} …")
        return self

    def flush(self):
        pass

    def close(self):
        pass


def _safe_float(v) -> float | None:
    """Convert pandas / numpy scalar to plain Python float, or None."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _row_to_event(row) -> dict:
    """
    Serialise a drilling record to a JSON-safe dict matching the
    streaming consumer schema in 04_streaming_scoring_and_alerts.py.
    """
    # ts: prefer ts_original; fall back to _ingest_ts
    ts = row.get("ts_original") or row.get("_ingest_ts")
    if ts is None:
        ts_str = None
    elif hasattr(ts, "isoformat"):
        ts_str = ts.isoformat()
    else:
        ts_str = str(ts)

    return {
        "well_id":  str(row.get("well_id", "")),
        "ts":       ts_str,
        "md":       _safe_float(row.get("md")),
        "tvd":      _safe_float(row.get("tvd")),
        "wob":      _safe_float(row.get("wob")),
        "rpm":      _safe_float(row.get("rpm")),
        "torque":   _safe_float(row.get("torque")),
        "spp":      _safe_float(row.get("spp")),
        "flow":     _safe_float(row.get("flow")),
        "hookload": _safe_float(row.get("hookload")),
        "rop":      _safe_float(row.get("rop")),
        "rig_state":str(row.get("rig_state", "")) if row.get("rig_state") else None,
    }


def replay_from_spark(well_id: str, max_rows: int, loop: bool,
                      speed: float, topic: str, bootstrap: str):
    """Load rows from Delta Bronze table and publish sequentially."""
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = SparkSession.builder.getOrCreate()

    def _fetch_rows(limit: int):
        q = (
            spark.table("drilling_demo_bronze.mseel_drilling_raw")
            .filter(F.col("well_id") == well_id)
            .orderBy("ts_original")
        )
        if limit > 0:
            q = q.limit(limit)
        return q.toPandas()

    producer = _make_producer(bootstrap)
    print(f"\n── Replay starting ──────────────────────────")
    print(f"   Well  : {well_id}")
    print(f"   Topic : {topic}")
    print(f"   Speed : {speed}s/record")
    print(f"   Loop  : {loop}")

    iteration = 0
    while True:
        iteration += 1
        df = _fetch_rows(max_rows)
        total = len(df)

        if total == 0:
            print(f"  ⚠ No rows found for well '{well_id}' in Bronze table — exiting.")
            break

        print(f"  [{iteration}] Replaying {total:,} records …")

        for idx, row in df.iterrows():
            event = _row_to_event(row.to_dict())
            producer.send(topic, event)

            if (idx + 1) % 500 == 0:
                producer.flush()
                print(
                    f"    Published {idx+1:,}/{total:,}  "
                    f"MD={event.get('md','-'):.0f} ft  "
                    f"ROP={event.get('rop','-')}"
                )

            time.sleep(speed)

        producer.flush()
        print(f"  ✓ Iteration {iteration} complete — {total:,} records published.")

        if not loop:
            break

    producer.close()
    print("\n✅ Replay producer finished.")


def replay_from_pandas(csv_path: str, well_id: str, speed: float,
                       topic: str, bootstrap: str, max_rows: int = 0):
    """
    Alternative: replay directly from a local CSV (no Spark needed).
    Useful for local dev/testing.
    """
    import pandas as pd

    print(f"\n── CSV Replay: {csv_path} ─────────────────────")
    df = pd.read_csv(csv_path)
    if max_rows > 0:
        df = df.head(max_rows)

    # Best-effort timestamp parse
    for col in df.columns:
        if "time" in col.lower() or "date" in col.lower():
            try:
                df = df.rename(columns={col: "ts_original"})
                df["ts_original"] = pd.to_datetime(df["ts_original"], errors="coerce")
                break
            except Exception:
                pass

    df["well_id"] = well_id
    producer = _make_producer(bootstrap)

    for idx, row in df.iterrows():
        producer.send(topic, _row_to_event(row.to_dict()))
        if (idx + 1) % 500 == 0:
            producer.flush()
            print(f"  {idx+1:,}/{len(df):,} published")
        time.sleep(speed)

    producer.flush()
    producer.close()
    print(f"✅ Replayed {len(df):,} records from CSV → {topic}")


def run():
    args = parse_args()

    print("=" * 60)
    print("MSEEL Drilling Replay Producer")
    print(f"Kafka  : {args.bootstrap}  →  {args.topic}")
    print("=" * 60)

    try:
        replay_from_spark(
            well_id=args.well,
            max_rows=args.max_rows,
            loop=args.loop,
            speed=args.speed,
            topic=args.topic,
            bootstrap=args.bootstrap,
        )
    except Exception as e:
        print(f"  Spark unavailable ({e}) — falling back to stdout stub.")
        # In pure local mode just demonstrate the event structure
        _StdoutProducer().send(args.topic, {
            "well_id": args.well, "ts": "2024-01-01T00:00:00Z",
            "md": 5000.0, "rop": 42.5, "wob": 15.0,
        })


if __name__ == "__main__":
    run()

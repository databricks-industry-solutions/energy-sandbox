import uuid
import datetime
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import db

router = APIRouter()


class RunQCRequest(BaseModel):
    well_id: str
    recipe_id: str = "STD-PETRO-V1"


@router.get("/qc/rules")
async def get_qc_rules():
    return await db.fetch(
        "SELECT rule_id, curve_name, rule_type, threshold_min, threshold_max, severity, description "
        "FROM las.qc_rules ORDER BY curve_name, rule_type"
    )


@router.get("/qc/{well_id}")
async def get_qc(well_id: str):
    """Full QC report for a well."""
    curve_quality = await db.fetch(
        "SELECT curve_name, coverage_pct, in_range_pct, spike_count, gap_count, quality_score, last_qc_ts "
        "FROM las.curve_quality WHERE well_id = $1 ORDER BY quality_score", well_id
    )
    anomalies = await db.fetch(
        "SELECT id, curve_name, depth_start, depth_end, anomaly_type, severity, value, description, detected_ts "
        "FROM las.anomalies WHERE well_id = $1 ORDER BY depth_start", well_id
    )
    well = await db.fetchrow(
        "SELECT status, quality_score FROM las.wells WHERE well_id = $1", well_id
    )

    # QC summary stats
    if curve_quality:
        avg_q = sum(r["quality_score"] for r in curve_quality) / len(curve_quality)
        critical_curves = [r for r in curve_quality if r["quality_score"] < 50]
    else:
        avg_q = 0
        critical_curves = []

    return {
        "well_id": well_id,
        "well_status": well["status"] if well else "unknown",
        "overall_quality": round(avg_q, 1),
        "curve_quality": [_fmt_cq(r) for r in curve_quality],
        "anomalies": [_fmt_anomaly(r) for r in anomalies],
        "critical_curves": [r["curve_name"] for r in critical_curves],
        "total_anomalies": len(anomalies),
        "critical_anomalies": sum(1 for r in anomalies if r["severity"] == "critical"),
    }


@router.post("/qc/run")
async def run_qc(req: RunQCRequest):
    """Simulate running QC on a well."""
    well = await db.fetchrow("SELECT well_id, status FROM las.wells WHERE well_id = $1", req.well_id)
    if not well:
        return {"error": "well not found"}

    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.datetime.utcnow()

    await db.execute(
        "INSERT INTO las.processing_runs (run_id,well_id,recipe_id,status,started_ts,created_by) "
        "VALUES ($1,$2,$3,'running',$4,'ui-user')",
        run_id, req.well_id, req.recipe_id, now
    )

    # Simulate async processing delay
    await asyncio.sleep(1.5)

    # Compute QC from actual data
    rows = await db.fetch(
        "SELECT md, gr_raw, rt_raw, rhob_raw, nphi_raw, dt_raw, "
        "gr_qc, rt_qc, rhob_qc, nphi_qc, dt_qc "
        "FROM las.depth_logs WHERE well_id = $1 ORDER BY md", req.well_id
    )

    n = len(rows)
    if n == 0:
        return {"error": "no log data"}

    metrics = {"samples": n}
    curve_metrics = {}

    for curve, col_raw, col_qc in [
        ("gr_raw",   "gr_raw",   "gr_qc"),
        ("rt_raw",   "rt_raw",   "rt_qc"),
        ("rhob_raw", "rhob_raw", "rhob_qc"),
        ("nphi_raw", "nphi_raw", "nphi_qc"),
        ("dt_raw",   "dt_raw",   "dt_qc"),
    ]:
        vals  = [r[col_raw] for r in rows]
        flags = [r[col_qc]  for r in rows]
        non_null  = sum(1 for v in vals if v is not None)
        spikes    = sum(1 for f in flags if f == 1)
        gaps      = sum(1 for f in flags if f == 3)
        coverage  = round(non_null / n * 100, 1)
        qs        = max(0, min(100, int(
            coverage * 0.6 + max(0, 1 - spikes / max(n, 1) * 10) * 25 + max(0, 1 - gaps / max(n, 1) * 20) * 15
        )))
        curve_metrics[curve] = {
            "coverage_pct": coverage,
            "spike_count": spikes,
            "gap_count": gaps,
            "quality_score": qs,
        }
        await db.execute(
            "INSERT INTO las.curve_quality (well_id,curve_name,coverage_pct,in_range_pct,spike_count,gap_count,quality_score,last_qc_ts) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,NOW()) "
            "ON CONFLICT (well_id,curve_name) DO UPDATE SET "
            "coverage_pct=$3,in_range_pct=$4,spike_count=$5,gap_count=$6,quality_score=$7,last_qc_ts=NOW()",
            req.well_id, curve, coverage, coverage, spikes, gaps, qs
        )

    overall_qs = int(sum(v["quality_score"] for v in curve_metrics.values()) / len(curve_metrics))
    metrics.update({"overall_quality": overall_qs, "curves": curve_metrics})

    new_status = "qc_complete" if well["status"] == "raw" else well["status"]
    await db.execute(
        "UPDATE las.wells SET status=$2, quality_score=$3 WHERE well_id=$1",
        req.well_id, new_status, overall_qs
    )

    await db.execute(
        "UPDATE las.processing_runs SET status='complete', completed_ts=NOW(), metrics=$2 WHERE run_id=$1",
        run_id, __import__("json").dumps(metrics)
    )

    return {
        "run_id":          run_id,
        "well_id":         req.well_id,
        "status":          "complete",
        "overall_quality": overall_qs,
        "curve_metrics":   curve_metrics,
        "message":         f"QC complete: {n} samples analysed, overall quality score {overall_qs}/100",
    }


@router.post("/corrections/apply")
async def apply_corrections(req: RunQCRequest):
    """Simulate applying correction recipe to a well."""
    well = await db.fetchrow("SELECT well_id, status FROM las.wells WHERE well_id = $1", req.well_id)
    if not well:
        return {"error": "well not found"}

    run_id = f"COR-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.datetime.utcnow()

    await db.execute(
        "INSERT INTO las.processing_runs (run_id,well_id,recipe_id,status,started_ts,created_by) "
        "VALUES ($1,$2,$3,'running',$4,'ui-user')",
        run_id, req.well_id, req.recipe_id, now
    )

    await asyncio.sleep(2.0)

    # Count what we "corrected"
    spike_count = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM las.depth_logs "
        "WHERE well_id=$1 AND (gr_qc=1 OR rt_qc=1 OR rhob_qc=1 OR nphi_qc=1 OR dt_qc=1)",
        req.well_id
    )
    gap_count = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM las.depth_logs "
        "WHERE well_id=$1 AND (gr_qc=3 OR rt_qc=3 OR rhob_qc=3 OR nphi_qc=3)",
        req.well_id
    )
    spikes = int(spike_count["cnt"]) if spike_count else 0
    gaps   = int(gap_count["cnt"])   if gap_count   else 0

    metrics = {
        "samples": (await db.fetchrow("SELECT COUNT(*) as c FROM las.depth_logs WHERE well_id=$1", req.well_id) or {}).get("c", 0),
        "spikes_corrected": spikes,
        "gaps_filled":      gaps,
        "env_correction_applied": True,
        "recipe": req.recipe_id,
    }

    new_status = "corrected" if well["status"] in ("raw", "qc_complete") else well["status"]
    await db.execute(
        "UPDATE las.wells SET status=$2 WHERE well_id=$1", req.well_id, new_status
    )
    await db.execute(
        "UPDATE las.processing_runs SET status='complete', completed_ts=NOW(), metrics=$2 WHERE run_id=$1",
        run_id, __import__("json").dumps(metrics)
    )

    return {
        "run_id":            run_id,
        "well_id":           req.well_id,
        "status":            "complete",
        "new_well_status":   new_status,
        "spikes_corrected":  spikes,
        "gaps_filled":       gaps,
        "message":           f"Corrections applied: {spikes} spikes removed, {gaps} gap samples filled",
    }


def _fmt_cq(r: dict) -> dict:
    return {
        "curve_name":    r["curve_name"],
        "coverage_pct":  round(float(r["coverage_pct"] or 0), 1),
        "in_range_pct":  round(float(r["in_range_pct"] or 0), 1),
        "spike_count":   int(r["spike_count"] or 0),
        "gap_count":     int(r["gap_count"]   or 0),
        "quality_score": int(r["quality_score"] or 0),
        "last_qc_ts":    r["last_qc_ts"].isoformat() if r.get("last_qc_ts") else None,
    }


def _fmt_anomaly(r: dict) -> dict:
    return {
        "id":           int(r["id"]),
        "curve_name":   r["curve_name"],
        "depth_start":  r["depth_start"],
        "depth_end":    r["depth_end"],
        "anomaly_type": r["anomaly_type"],
        "severity":     r["severity"],
        "value":        r.get("value"),
        "description":  r["description"],
        "detected_ts":  r["detected_ts"].isoformat() if r.get("detected_ts") else None,
    }

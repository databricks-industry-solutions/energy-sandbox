from fastapi import APIRouter
from ..db import db

router = APIRouter()


@router.get("/wells")
async def list_wells():
    wells = await db.fetch(
        "SELECT w.well_id, w.well_name, w.field_name, w.basin, w.county, w.state, "
        "w.api_number, w.lat, w.lon, w.kb_elevation_ft, w.total_depth_ft, "
        "w.spud_date, w.well_type, w.status, w.quality_score, w.curve_count, w.notes, "
        "w.ingest_ts, "
        "COALESCE(a.anomaly_count, 0) as anomaly_count, "
        "COALESCE(a.critical_count, 0) as critical_count "
        "FROM las.wells w "
        "LEFT JOIN ("
        "  SELECT well_id, COUNT(*) as anomaly_count, "
        "  COUNT(*) FILTER (WHERE severity='critical') as critical_count "
        "  FROM las.anomalies GROUP BY well_id"
        ") a ON a.well_id = w.well_id "
        "ORDER BY w.quality_score DESC"
    )
    return [_fmt_well(w) for w in wells]


@router.get("/wells/{well_id}")
async def get_well(well_id: str):
    well = await db.fetchrow(
        "SELECT w.*, COALESCE(a.anomaly_count, 0) as anomaly_count "
        "FROM las.wells w "
        "LEFT JOIN (SELECT well_id, COUNT(*) as anomaly_count FROM las.anomalies GROUP BY well_id) a "
        "ON a.well_id = w.well_id "
        "WHERE w.well_id = $1", well_id
    )
    if not well:
        return {"error": "not found"}

    curve_quality = await db.fetch(
        "SELECT curve_name, coverage_pct, in_range_pct, spike_count, gap_count, quality_score "
        "FROM las.curve_quality WHERE well_id = $1 ORDER BY curve_name", well_id
    )
    formations = await db.fetch(
        "SELECT formation_name, top_md, base_md, zone_type, lithology_desc "
        "FROM las.formation_tops WHERE well_id = $1 ORDER BY top_md", well_id
    )
    anomalies = await db.fetch(
        "SELECT curve_name, depth_start, depth_end, anomaly_type, severity, value, description "
        "FROM las.anomalies WHERE well_id = $1 ORDER BY depth_start", well_id
    )
    runs = await db.fetch(
        "SELECT run_id, recipe_id, status, started_ts, completed_ts, metrics "
        "FROM las.processing_runs WHERE well_id = $1 ORDER BY started_ts DESC LIMIT 5", well_id
    )

    return {
        **_fmt_well(well),
        "curve_quality": [dict(r) for r in curve_quality],
        "formations": [dict(r) for r in formations],
        "anomalies": [dict(r) for r in anomalies],
        "processing_runs": [_fmt_run(r) for r in runs],
    }


@router.get("/wells/{well_id}/summary")
async def well_summary(well_id: str):
    stats = await db.fetchrow(
        "SELECT COUNT(*) as sample_count, MIN(md) as min_md, MAX(md) as max_md, "
        "AVG(gr_raw) as avg_gr, AVG(rhob_raw) as avg_rhob, AVG(nphi_raw) as avg_nphi, "
        "SUM(CASE WHEN gr_qc > 0 THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as gr_qc_pct, "
        "SUM(CASE WHEN rhob_qc > 0 THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as rhob_qc_pct "
        "FROM las.depth_logs WHERE well_id = $1", well_id
    )
    return stats or {}


def _fmt_well(w: dict) -> dict:
    return {
        "well_id":        w["well_id"],
        "well_name":      w["well_name"],
        "field_name":     w.get("field_name"),
        "basin":          w.get("basin"),
        "county":         w.get("county"),
        "state":          w.get("state"),
        "api_number":     w.get("api_number"),
        "lat":            w.get("lat"),
        "lon":            w.get("lon"),
        "kb_elevation_ft":w.get("kb_elevation_ft"),
        "total_depth_ft": w.get("total_depth_ft"),
        "spud_date":      w["spud_date"].isoformat() if w.get("spud_date") else None,
        "well_type":      w.get("well_type"),
        "status":         w.get("status"),
        "quality_score":  w.get("quality_score"),
        "curve_count":    w.get("curve_count"),
        "notes":          w.get("notes"),
        "ingest_ts":      w["ingest_ts"].isoformat() if w.get("ingest_ts") else None,
        "anomaly_count":  w.get("anomaly_count", 0),
        "critical_count": w.get("critical_count", 0),
    }


def _fmt_run(r: dict) -> dict:
    import json
    return {
        "run_id":       r["run_id"],
        "recipe_id":    r["recipe_id"],
        "status":       r["status"],
        "started_ts":   r["started_ts"].isoformat() if r.get("started_ts") else None,
        "completed_ts": r["completed_ts"].isoformat() if r.get("completed_ts") else None,
        "metrics":      json.loads(r["metrics"]) if r.get("metrics") else {},
    }

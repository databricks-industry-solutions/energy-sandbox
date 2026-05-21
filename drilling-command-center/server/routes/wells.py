import time
from fastapi import APIRouter
from ..db import db

router = APIRouter()

# Small in-process cache. /api/wells is hit by Overview, Governance KPI strip,
# Supervisor tab, and the Genie/Expert flows — caching for 10s collapses the
# duplicate work without making the demo feel stale.
_WELLS_CACHE: tuple[float, list] | None = None
_WELLS_TTL_S = 60


@router.get("/wells/alerts")
async def fleet_alerts():
    """Surface drilling-ops issues for the Overview alerts ticker.
    Pulls from las.drilling_operations and emits a sorted feed of NPT
    spikes, BHA-health degradations, incidents, and supply-chain delays."""
    rows = await db.fetch(
        "SELECT d_op.well_id, w.well_name, w.basin, d_op.rig_name, d_op.drilling_phase, "
        "       d_op.npt_hours_last_30d, d_op.esp_health_pct, d_op.mud_pump_health_pct, "
        "       d_op.last_incident_severity, d_op.last_incident_desc, d_op.last_incident_date, "
        "       d_op.supply_chain_status, d_op.days_to_next_casing "
        "FROM las.drilling_operations d_op "
        "LEFT JOIN las.wells w ON w.well_id = d_op.well_id"
    )
    alerts = []
    for r in rows:
        wid = r["well_id"]
        wname = r.get("well_name") or wid
        npt = float(r.get("npt_hours_last_30d") or 0)
        esp = int(r.get("esp_health_pct") or 100)
        pump = int(r.get("mud_pump_health_pct") or 100)
        sev_inc = (r.get("last_incident_severity") or "").lower()
        sup = (r.get("supply_chain_status") or "").lower()
        if npt > 60:
            alerts.append({"well_id": wid, "well_name": wname, "severity": "critical",
                           "kind": "NPT", "msg": f"NPT {npt:.0f}h in last 30d — schedule risk",
                           "ts": r.get("last_incident_date")})
        elif npt > 30:
            alerts.append({"well_id": wid, "well_name": wname, "severity": "warn",
                           "kind": "NPT", "msg": f"NPT {npt:.0f}h trending elevated",
                           "ts": r.get("last_incident_date")})
        if esp < 80:
            alerts.append({"well_id": wid, "well_name": wname, "severity": "warn",
                           "kind": "BHA", "msg": f"ESP health {esp}% — workover candidate",
                           "ts": r.get("last_incident_date")})
        if pump < 80:
            alerts.append({"well_id": wid, "well_name": wname, "severity": "warn",
                           "kind": "BHA", "msg": f"Mud pump health {pump}% — service window",
                           "ts": r.get("last_incident_date")})
        if sev_inc in ("major", "critical"):
            alerts.append({"well_id": wid, "well_name": wname,
                           "severity": "critical" if sev_inc == "critical" else "warn",
                           "kind": "Incident",
                           "msg": r.get("last_incident_desc") or "Incident reported",
                           "ts": r.get("last_incident_date")})
        if "delayed" in sup:
            alerts.append({"well_id": wid, "well_name": wname, "severity": "warn",
                           "kind": "Supply",
                           "msg": f"Supply chain · {r.get('supply_chain_status')}",
                           "ts": r.get("last_incident_date")})
    # critical first, then by date desc
    sev_rank = {"critical": 0, "warn": 1, "info": 2}
    alerts.sort(key=lambda a: (sev_rank.get(a["severity"], 9),
                               -(a["ts"].toordinal() if hasattr(a.get("ts"), "toordinal") else 0)))
    # serialise dates
    for a in alerts:
        ts = a.get("ts")
        a["ts"] = ts.isoformat() if hasattr(ts, "isoformat") else None
    return {"count": len(alerts), "alerts": alerts[:12]}


@router.get("/wells")
async def list_wells():
    global _WELLS_CACHE
    if _WELLS_CACHE and time.time() - _WELLS_CACHE[0] < _WELLS_TTL_S:
        return _WELLS_CACHE[1]
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
    formatted = [_fmt_well(w) for w in wells]
    _WELLS_CACHE = (time.time(), formatted)
    return formatted


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

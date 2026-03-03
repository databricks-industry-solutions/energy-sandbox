from fastapi import APIRouter, Query
from ..db import db

router = APIRouter()


@router.get("/logs/{well_id}")
async def get_logs(
    well_id: str,
    depth_min: float = Query(default=None),
    depth_max: float = Query(default=None),
    thin: int = Query(default=1, description="Thinning factor: 1=all, 2=every 2nd, etc."),
):
    # Determine depth range
    if depth_min is None or depth_max is None:
        bounds = await db.fetchrow(
            "SELECT MIN(md) as dmin, MAX(md) as dmax FROM las.depth_logs WHERE well_id = $1",
            well_id
        )
        if not bounds:
            return {"error": "no data"}
        depth_min = bounds["dmin"] or 5000.0
        depth_max = bounds["dmax"] or 10000.0

    rows = await db.fetch(
        "SELECT md, gr_raw, rt_raw, rxo_raw, rhob_raw, nphi_raw, dt_raw, cali_raw, sp_raw, pef_raw, "
        "gr_qc, rt_qc, rhob_qc, nphi_qc, dt_qc, "
        "gr_c, rt_c, rhob_c, nphi_c, dt_c, vcl, phi_total, phi_eff, sw "
        "FROM las.depth_logs WHERE well_id = $1 AND md BETWEEN $2 AND $3 ORDER BY md",
        well_id, depth_min, depth_max
    )

    if not rows:
        return {"well_id": well_id, "md": [], "curves": {}, "formations": []}

    # Apply thinning
    if thin > 1:
        rows = rows[::thin]

    # Convert columnar format (efficient for rendering)
    md       = [r["md"] for r in rows]
    curves = {
        "gr_raw":   _clean(r["gr_raw"]   for r in rows),
        "rt_raw":   _clean(r["rt_raw"]   for r in rows),
        "rxo_raw":  _clean(r["rxo_raw"]  for r in rows),
        "rhob_raw": _clean(r["rhob_raw"] for r in rows),
        "nphi_raw": _clean(r["nphi_raw"] for r in rows),
        "dt_raw":   _clean(r["dt_raw"]   for r in rows),
        "cali_raw": _clean(r["cali_raw"] for r in rows),
        "sp_raw":   _clean(r["sp_raw"]   for r in rows),
        "pef_raw":  _clean(r["pef_raw"]  for r in rows),
        "gr_qc":    [r["gr_qc"]   for r in rows],
        "rt_qc":    [r["rt_qc"]   for r in rows],
        "rhob_qc":  [r["rhob_qc"] for r in rows],
        "nphi_qc":  [r["nphi_qc"] for r in rows],
        "dt_qc":    [r["dt_qc"]   for r in rows],
        # Corrected
        "gr_c":     _clean(r["gr_c"]     for r in rows),
        "rt_c":     _clean(r["rt_c"]     for r in rows),
        "rhob_c":   _clean(r["rhob_c"]   for r in rows),
        "nphi_c":   _clean(r["nphi_c"]   for r in rows),
        "dt_c":     _clean(r["dt_c"]     for r in rows),
        # Derived
        "vcl":      _clean(r["vcl"]      for r in rows),
        "phi_eff":  _clean(r["phi_eff"]  for r in rows),
        "sw":       _clean(r["sw"]       for r in rows),
    }

    # Determine availability
    has_raw       = any(v is not None for v in curves["gr_raw"])
    has_corrected = any(v is not None for v in curves["gr_c"])
    has_derived   = any(v is not None for v in curves["vcl"])

    # Formation tops
    formations = await db.fetch(
        "SELECT formation_name, top_md, base_md, zone_type FROM las.formation_tops "
        "WHERE well_id = $1 AND top_md BETWEEN $2 AND $3 ORDER BY top_md",
        well_id, depth_min - 100, depth_max + 100
    )

    return {
        "well_id":       well_id,
        "depth_range":   [depth_min, depth_max],
        "sample_count":  len(md),
        "md":            md,
        "curves":        curves,
        "formations":    [dict(f) for f in formations],
        "has_raw":       has_raw,
        "has_corrected": has_corrected,
        "has_derived":   has_derived,
    }


@router.get("/logs/{well_id}/overview")
async def logs_overview(well_id: str):
    """Thin overview for the full well (every 10th sample for navigator)."""
    rows = await db.fetch(
        "SELECT md, gr_raw, gr_c, rhob_raw, nphi_raw, rt_raw, sw "
        "FROM las.depth_logs WHERE well_id = $1 ORDER BY md",
        well_id
    )
    # every 5th row
    rows = rows[::5]
    return {
        "well_id": well_id,
        "md":      [r["md"] for r in rows],
        "gr":      _clean(r["gr_c"] if r["gr_c"] is not None else r["gr_raw"] for r in rows),
        "rhob":    _clean(r["rhob_raw"] for r in rows),
        "nphi":    _clean(r["nphi_raw"] for r in rows),
        "rt":      _clean(r["rt_raw"]  for r in rows),
        "sw":      _clean(r["sw"]      for r in rows),
    }


def _clean(gen) -> list:
    result = []
    for v in gen:
        if v is None or (isinstance(v, float) and (v != v)):  # None or NaN
            result.append(None)
        else:
            result.append(float(v))
    return result

"""Subsurface scene endpoint: wells + reservoirs + samples + formations, all
geo-normalized for the 3D viewer."""
import math
import os
from fastapi import APIRouter
from ..db import db

router = APIRouter()

CATALOG = os.getenv("ADME_CATALOG", "adme_adb_sbx_scus_dbx_ws_1")
SCHEMA  = os.getenv("ADME_SCHEMA", "adme_client_demo")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "186af4be97756033")


def _sql():
    from databricks import sql as dsql
    from databricks.sdk.core import Config
    cfg = Config()
    host = (os.getenv("DATABRICKS_HOST") or cfg.host or "").replace("https://", "").rstrip("/")
    return dsql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


def _synth_trajectory(well_id: str, td_ft: float, tvd_ft: float, well_type: str) -> list[tuple[float, float, float]]:
    """Return [(x, y_depth, z), ...] in ft. X/Z are horizontal offsets from surface in ft.
    For vertical wells: straight down. For deviated/horizontal: synthesized build-and-hold."""
    td = max(1.0, td_ft)
    tvd = max(1.0, min(tvd_ft or td, td))
    horiz = math.sqrt(max(0.0, td * td - tvd * tvd))
    # Azimuth hashed off well_id for consistency
    az = (abs(hash(well_id)) % 360) * math.pi / 180.0
    points: list[tuple[float, float, float]] = []
    if well_type == "vertical" or horiz < 100:
        for i in range(11):
            y = -td * i / 10
            points.append((0.0, y, 0.0))
        return points
    # Build-and-hold synthesis: kick-off at 30% of TVD, build through to 70% of MD, then hold
    kop_depth = tvd * 0.3
    build_end_depth = tvd * 0.7
    for i in range(31):
        s = i / 30  # fraction of MD
        md = td * s
        if md <= kop_depth:
            y = -md
            x = 0.0
        elif md <= build_end_depth:
            # Interpolate build section — arc from kop straight down to build_end with displacement
            t = (md - kop_depth) / (build_end_depth - kop_depth)
            # Use sin/cos to smoothly transition to the hold angle
            theta = t * math.pi / 2  # 0 → 90° of build
            # Approximate build arc
            disp = horiz * (1 - math.cos(theta)) * 0.5
            tvd_gain = (build_end_depth - kop_depth) * math.sin(theta) / math.sin(math.pi / 2)
            y = -(kop_depth + tvd_gain * 0.8)
            x = disp
        else:
            # Hold at inclination
            t = (md - build_end_depth) / (td - build_end_depth) if td > build_end_depth else 0
            y = -(build_end_depth * 0.8 + t * (tvd - build_end_depth * 0.8))
            x = horiz * 0.5 + t * horiz * 0.5
        points.append((x * math.cos(az), y, x * math.sin(az)))
    return points


def _osdu_fetch(sql_text: str) -> list[dict]:
    try:
        with _sql() as c, c.cursor() as cur:
            cur.execute(sql_text)
            return cur.fetchall_arrow().to_pylist()
    except Exception as e:
        print(f"OSDU fetch error: {e}")
        return []


VS_ENDPOINT = os.getenv("VS_ENDPOINT", "subsurface-vs")
VS_INDEX    = os.getenv("VS_INDEX", f"{CATALOG}.{SCHEMA}.wellbore_vs_index")


def _vs_search_sync(query_text: str, k: int) -> list[dict]:
    from databricks.vector_search.client import VectorSearchClient
    c = VectorSearchClient(disable_notice=True)
    idx = c.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
    res = idx.similarity_search(
        query_text=query_text,
        columns=["well_key", "well_name", "platform", "primary_reservoir", "drilling_result"],
        num_results=k,
    )
    rows = []
    if res and "result" in res:
        data = res["result"].get("data_array", [])
        cols = [c["name"] for c in res["manifest"]["columns"]]
        for r in data:
            rows.append(dict(zip(cols, r)))
    return rows


@router.get("/subsurface/similar/{well_id}")
async def similar_wells(well_id: str, k: int = 3):
    """Return k wells most similar to the given one using Vector Search over OSDU metadata."""
    # Seed well context from local DuckDB
    w = await db.fetchrow(
        "SELECT well_name, basin, notes FROM las.wells WHERE well_id = $1", well_id
    )
    if not w:
        return {"well_id": well_id, "results": [], "error": "well not found"}
    seed_text = f"{w.get('well_name','')} {w.get('basin','')} {w.get('notes','')}"[:500]
    import asyncio as _a
    try:
        rows = await _a.to_thread(_vs_search_sync, seed_text, int(k) + 1)
    except Exception as e:
        return {"well_id": well_id, "results": [], "error": str(e)}
    # Remove seed itself if present
    cleaned = []
    for r in rows:
        wk = str(r.get("well_key", ""))
        if well_id.startswith("OSDU-") and wk and wk.endswith(well_id[5:]):
            continue
        cleaned.append({
            "well_key":          wk,
            "well_name":         r.get("well_name"),
            "platform":          r.get("platform"),
            "primary_reservoir": r.get("primary_reservoir"),
            "drilling_result":   r.get("drilling_result"),
            "score":             float(r.get("score", 0)),
        })
    return {"well_id": well_id, "seed": seed_text, "results": cleaned[:int(k)]}


@router.get("/subsurface/scene")
async def scene():
    """Returns the full 3D scene: wells with trajectories, reservoirs, samples, formations."""
    # Wells from Lakebase (local DuckDB) for consistent data
    wells = await db.fetch(
        "SELECT well_id, well_name, lat, lon, total_depth_ft, well_type, status, quality_score, notes "
        "FROM las.wells ORDER BY well_id"
    )
    # Formations from DuckDB
    formations = await db.fetch(
        "SELECT well_id, formation_name, top_md, base_md, zone_type "
        "FROM las.formation_tops ORDER BY well_id, top_md"
    )

    # Reservoirs + rock_and_fluid from OSDU UC
    reservoirs = _osdu_fetch(f"""
        SELECT
          record_id,
          silver_payload:data.ReservoirName::string AS name,
          silver_payload:data.FormationName::string AS formation,
          silver_payload:data.DiscoveryYear::int AS discovery_year,
          silver_payload:data.OriginalOilInPlace.value::double AS ooip_mm_sm3,
          silver_payload:data.ReservoirDepth.value::double AS depth_m,
          silver_payload:data.InitialReservoirPressure.value::double AS pressure_bar,
          silver_payload:data.InitialReservoirTemperature.value::double AS temp_c
        FROM `{CATALOG}`.`{SCHEMA}`.silver_reservoir
    """)
    samples = _osdu_fetch(f"""
        SELECT
          record_id,
          silver_payload:data.SampleID::string AS sample_id,
          silver_payload:data.FormationName::string AS formation,
          silver_payload:data.SampleDepth.value::double AS depth_m,
          silver_payload:data.Porosity::double AS porosity,
          silver_payload:data.Permeability.value::double AS perm_md,
          silver_payload:data.WaterSaturation::double AS sw,
          silver_payload:data.OilSaturation::double AS so
        FROM `{CATALOG}`.`{SCHEMA}`.silver_rock_and_fluid
    """)

    # Build per-well trajectories + lookup formations
    fmt_by_well: dict[str, list[dict]] = {}
    for f in formations:
        fmt_by_well.setdefault(f["well_id"], []).append(f)

    well_payload = []
    for w in wells:
        td = float(w.get("total_depth_ft") or 10000.0)
        tvd = td * 0.95  # Approximation; OSDU TVD not in our DuckDB snapshot
        if w.get("well_type") == "horizontal":
            tvd = td * 0.7
        elif w.get("well_type") == "deviated":
            tvd = td * 0.85
        traj = _synth_trajectory(w["well_id"], td, tvd, w.get("well_type") or "vertical")
        well_payload.append({
            "well_id":        w["well_id"],
            "well_name":      w["well_name"],
            "lat":            w.get("lat"),
            "lon":            w.get("lon"),
            "total_depth_ft": td,
            "tvd_ft":         tvd,
            "well_type":      w.get("well_type"),
            "status":         w.get("status"),
            "quality_score":  w.get("quality_score"),
            "trajectory":     traj,
            "formations":     fmt_by_well.get(w["well_id"], []),
        })

    # Reservoir bounds for rendering as faceted grid cells
    res_payload = []
    for i, r in enumerate(reservoirs):
        depth_m = float(r.get("depth_m") or 2500)
        depth_ft = depth_m * 3.28084
        ooip = float(r.get("ooip_mm_sm3") or 50)
        # Lateral extent scales with OOIP (bigger reservoir = bigger box)
        extent_ft = 800 + math.sqrt(ooip) * 400
        thickness_ft = 200 + ooip * 5
        # Position reservoirs around scene centroid, offset radially by index
        ang = i * 2 * math.pi / max(len(reservoirs), 1)
        cx_ft = math.cos(ang) * 2000
        cz_ft = math.sin(ang) * 2000
        res_payload.append({
            "record_id": r.get("record_id"),
            "name": r.get("name"),
            "formation": r.get("formation"),
            "ooip_mm_sm3": ooip,
            "depth_m": depth_m,
            "depth_ft": depth_ft,
            "pressure_bar": r.get("pressure_bar"),
            "temp_c": r.get("temp_c"),
            "cx_ft": cx_ft,
            "cz_ft": cz_ft,
            "extent_ft": extent_ft,
            "thickness_ft": thickness_ft,
        })

    sample_payload = []
    for i, s in enumerate(samples):
        depth_m = float(s.get("depth_m") or 1000)
        depth_ft = depth_m * 3.28084
        ang = i * 2 * math.pi / max(len(samples), 1) + math.pi / 6
        cx_ft = math.cos(ang) * 1400
        cz_ft = math.sin(ang) * 1400
        sample_payload.append({
            "record_id":  s.get("record_id"),
            "sample_id":  s.get("sample_id"),
            "formation":  s.get("formation"),
            "depth_m":    depth_m,
            "depth_ft":   depth_ft,
            "porosity":   s.get("porosity"),
            "perm_md":    s.get("perm_md"),
            "sw":         s.get("sw"),
            "so":         s.get("so"),
            "cx_ft":      cx_ft,
            "cz_ft":      cz_ft,
        })

    return {
        "wells":      well_payload,
        "reservoirs": res_payload,
        "samples":    sample_payload,
    }

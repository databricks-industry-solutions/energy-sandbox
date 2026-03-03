import math
import random
import datetime

CREATE_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS las;

CREATE TABLE IF NOT EXISTS las.wells (
    well_id         VARCHAR(64) PRIMARY KEY,
    well_name       VARCHAR(128) NOT NULL,
    field_name      VARCHAR(128),
    basin           VARCHAR(64),
    county          VARCHAR(64),
    state           VARCHAR(32),
    api_number      VARCHAR(32),
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    kb_elevation_ft DOUBLE PRECISION,
    total_depth_ft  DOUBLE PRECISION,
    spud_date       DATE,
    well_type       VARCHAR(32) DEFAULT 'vertical',
    status          VARCHAR(32) DEFAULT 'raw',
    quality_score   INTEGER DEFAULT 0,
    curve_count     INTEGER DEFAULT 0,
    notes           TEXT,
    ingest_ts       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS las.formation_tops (
    well_id         VARCHAR(64) NOT NULL,
    formation_name  VARCHAR(64) NOT NULL,
    top_md          DOUBLE PRECISION NOT NULL,
    base_md         DOUBLE PRECISION,
    zone_type       VARCHAR(32),
    lithology_desc  VARCHAR(128),
    PRIMARY KEY (well_id, formation_name)
);

CREATE TABLE IF NOT EXISTS las.depth_logs (
    well_id     VARCHAR(64) NOT NULL,
    md          DOUBLE PRECISION NOT NULL,
    -- Raw curves
    gr_raw      DOUBLE PRECISION,
    rt_raw      DOUBLE PRECISION,
    rxo_raw     DOUBLE PRECISION,
    rhob_raw    DOUBLE PRECISION,
    nphi_raw    DOUBLE PRECISION,
    dt_raw      DOUBLE PRECISION,
    cali_raw    DOUBLE PRECISION,
    sp_raw      DOUBLE PRECISION,
    pef_raw     DOUBLE PRECISION,
    -- QC flags: 0=OK 1=spike 2=range 3=gap 4=noisy
    gr_qc       SMALLINT DEFAULT 0,
    rt_qc       SMALLINT DEFAULT 0,
    rhob_qc     SMALLINT DEFAULT 0,
    nphi_qc     SMALLINT DEFAULT 0,
    dt_qc       SMALLINT DEFAULT 0,
    -- Corrected curves (set after processing)
    gr_c        DOUBLE PRECISION,
    rt_c        DOUBLE PRECISION,
    rhob_c      DOUBLE PRECISION,
    nphi_c      DOUBLE PRECISION,
    dt_c        DOUBLE PRECISION,
    -- Petrophysical derived (gold layer)
    vcl         DOUBLE PRECISION,
    phi_total   DOUBLE PRECISION,
    phi_eff     DOUBLE PRECISION,
    sw          DOUBLE PRECISION,
    PRIMARY KEY (well_id, md)
);

CREATE INDEX IF NOT EXISTS idx_depth_logs_well ON las.depth_logs (well_id);

CREATE TABLE IF NOT EXISTS las.curve_quality (
    well_id         VARCHAR(64) NOT NULL,
    curve_name      VARCHAR(32) NOT NULL,
    coverage_pct    DOUBLE PRECISION DEFAULT 0,
    in_range_pct    DOUBLE PRECISION DEFAULT 0,
    spike_count     INTEGER DEFAULT 0,
    gap_count       INTEGER DEFAULT 0,
    quality_score   INTEGER DEFAULT 0,
    last_qc_ts      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (well_id, curve_name)
);

CREATE TABLE IF NOT EXISTS las.qc_rules (
    rule_id     SERIAL PRIMARY KEY,
    curve_name  VARCHAR(32) NOT NULL,
    rule_type   VARCHAR(32) NOT NULL,
    threshold_min DOUBLE PRECISION,
    threshold_max DOUBLE PRECISION,
    severity    VARCHAR(16) DEFAULT 'warning',
    description VARCHAR(256)
);

CREATE TABLE IF NOT EXISTS las.processing_recipes (
    recipe_id   VARCHAR(64) PRIMARY KEY,
    name        VARCHAR(128) NOT NULL,
    description TEXT,
    version     VARCHAR(16) DEFAULT '1.0',
    category    VARCHAR(32),
    steps       JSONB,
    is_active   BOOLEAN DEFAULT TRUE,
    created_ts  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS las.processing_runs (
    run_id      VARCHAR(64) PRIMARY KEY,
    well_id     VARCHAR(64),
    recipe_id   VARCHAR(64),
    status      VARCHAR(16) DEFAULT 'pending',
    started_ts  TIMESTAMPTZ,
    completed_ts TIMESTAMPTZ,
    metrics     JSONB,
    created_by  VARCHAR(64) DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS las.anomalies (
    id          BIGSERIAL PRIMARY KEY,
    well_id     VARCHAR(64) NOT NULL,
    curve_name  VARCHAR(32) NOT NULL,
    depth_start DOUBLE PRECISION,
    depth_end   DOUBLE PRECISION,
    anomaly_type VARCHAR(32),
    severity    VARCHAR(16) DEFAULT 'warning',
    value       DOUBLE PRECISION,
    description VARCHAR(256),
    detected_ts TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomalies_well ON las.anomalies (well_id);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Formation zone definitions
# ─────────────────────────────────────────────────────────────────────────────
_ZONES = [
    # name, top, base, gr_μ, gr_σ, log10_rt_μ, log10_rt_σ, rhob_μ, rhob_σ, nphi_μ, nphi_σ, dt_μ, dt_σ, type, pef_μ, sp_μ
    ("Entrada",      5000, 6000,  95, 18, 0.48, 0.18, 2.42, 0.04, 0.320, 0.030, 95, 7,  "shale",    3.4, -20),
    ("Morrison",     6000, 6800,  55, 22, 0.90, 0.28, 2.37, 0.05, 0.220, 0.035, 84, 6,  "sand",     2.8, -45),
    ("Todilto",      6800, 7500,  12,  6, 2.35, 0.35, 2.68, 0.03, 0.038, 0.015, 56, 3,  "carbonate",4.9, -60),
    ("Brushy Basin", 7500, 8000,  88, 16, 0.40, 0.16, 2.44, 0.04, 0.340, 0.028, 92, 6,  "shale",    3.3, -22),
    ("Westwater",    8000, 9200,  28, 13, 2.10, 0.40, 2.18, 0.05, 0.135, 0.028, 70, 5,  "reservoir",2.2, -75),
    ("Salt Wash",    9200,10000,  62, 25, 1.15, 0.36, 2.32, 0.05, 0.195, 0.035, 81, 6,  "fluvial",  2.6, -50),
]

_WELLS = [
    # well_id, well_name, field, basin, county, state, api, lat, lon, kb_ft, td_ft, spud, type, status, quality, notes
    ("BAKER-001", "Baker 1-A", "Blanco", "San Juan", "Rio Arriba", "NM",
     "30-039-00001", 36.72, -107.58, 5842, 10000, "2022-03-15", "vertical",   "gold",      88,
     "Showcase well: full petrophysical processing and derived curves"),
    ("BAKER-002", "Baker 2-B", "Blanco", "San Juan", "Rio Arriba", "NM",
     "30-039-00002", 36.69, -107.54, 5860, 10000, "2022-06-20", "vertical",   "corrected", 72,
     "Corrections applied; washout zones in Brushy Basin shale affect RHOB/NPHI"),
    ("CONOCO-7H", "Conoco 7-H", "Wamsutter", "Green River", "Sweetwater", "WY",
     "49-037-00701", 41.68,  -107.92, 6105,  9800, "2023-01-10", "horizontal","qc_complete",61,
     "No DT curve available — synthetic sonic needed for geomechanics bundle"),
    ("MARATHON-15X", "Marathon 15-X", "Midland", "Permian Basin", "Midland", "TX",
     "42-329-15000", 31.95,  -102.11, 2740, 10000, "2023-09-05", "vertical",   "raw",       0,
     "Freshly ingested — QC not yet run"),
    ("SHELL-3D", "Shell 3-D", "East Texas", "East Texas", "Nacogdoches", "TX",
     "42-347-03000", 31.53,  -94.58,  180,  10000, "2021-11-30", "deviated",  "gold",      95,
     "Best-in-class QC; all correction modules applied; full derived curve bundle"),
    ("PIONEER-22S", "Pioneer 22-S", "Edwards", "Permian Basin", "Irion", "TX",
     "42-235-22000", 31.22,  -100.93, 2560,  9800, "2022-08-14", "vertical",  "corrected", 78,
     "Carbonate well; Edwards Lime karst porosity; tight matrix corrections applied"),
]

_RECIPES = [
    {
        "recipe_id": "STD-PETRO-V1",
        "name": "Corporate Standard Petrophysical",
        "description": "Full QC + environmental corrections + Archie Sw + porosity. Validated against core from Westwater interval.",
        "version": "1.2",
        "category": "standard",
        "steps": [
            {"step": 1, "module": "depth_alignment",    "params": {"method": "linear_interp", "grid_spacing_ft": 0.5}},
            {"step": 2, "module": "despiking",          "params": {"window": 11, "threshold_sigma": 3.5}},
            {"step": 3, "module": "env_corrections",    "params": {"borehole_diameter_in": 8.5, "mud_type": "WBM"}},
            {"step": 4, "module": "gap_fill",           "params": {"short_gap_ft": 10, "method": "linear", "long_gap_model": "xgboost"}},
            {"step": 5, "module": "curve_harmonization","params": {"gr_min": 20, "gr_max": 120, "unit": "API"}},
            {"step": 6, "module": "petrophysics",       "params": {"vcl_method": "linear_gr", "phi_method": "density", "sw_method": "archie",
                                                                    "rw_ohmm": 0.05, "m": 2.0, "n": 2.0, "a": 1.0}},
        ],
    },
    {
        "recipe_id": "FAST-DRILL-V1",
        "name": "Fast Turnaround Drilling Support",
        "description": "Rapid QC + depth alignment only. Designed for real-time drilling decisions. No ML gap filling.",
        "version": "1.0",
        "category": "fast",
        "steps": [
            {"step": 1, "module": "depth_alignment", "params": {"method": "linear_interp", "grid_spacing_ft": 1.0}},
            {"step": 2, "module": "despiking",       "params": {"window": 7, "threshold_sigma": 4.0}},
            {"step": 3, "module": "gap_fill",        "params": {"short_gap_ft": 5, "method": "linear", "long_gap_model": "none"}},
        ],
    },
    {
        "recipe_id": "HIFI-RSVR-V1",
        "name": "High Fidelity Reservoir Simulation",
        "description": "Maximum-accuracy workflow for reservoir modelling inputs. Includes ML synthetic sonic and advanced Sw from modified Archie.",
        "version": "2.1",
        "category": "high_fidelity",
        "steps": [
            {"step": 1, "module": "depth_alignment",    "params": {"method": "dtw", "grid_spacing_ft": 0.5}},
            {"step": 2, "module": "despiking",          "params": {"window": 15, "threshold_sigma": 2.8}},
            {"step": 3, "module": "env_corrections",    "params": {"borehole_diameter_in": 8.5, "mud_type": "WBM", "invasion_correction": True}},
            {"step": 4, "module": "gap_fill",           "params": {"short_gap_ft": 20, "method": "spline", "long_gap_model": "deepnet"}},
            {"step": 5, "module": "synthetic_dt",       "params": {"model": "xgboost", "features": ["gr_c","rhob_c","nphi_c","rt_c"]}},
            {"step": 6, "module": "curve_harmonization","params": {"gr_min": 20, "gr_max": 120, "z_score_normalize": True}},
            {"step": 7, "module": "petrophysics",       "params": {"vcl_method": "linear_gr", "phi_method": "neutron_density",
                                                                    "sw_method": "modified_archie", "rw_ohmm": 0.05, "m": 2.1, "n": 2.0, "a": 0.81}},
            {"step": 8, "module": "geomechanics",       "params": {"poisson_method": "vp_vs", "ucs_method": "empirical_sonic"}},
        ],
    },
]

_QC_RULES = [
    ("gr_raw",   "range",         0,    250,   "warning",  "GR must be within 0-250 API"),
    ("gr_raw",   "null_ratio",    0.95, None,  "critical", "GR coverage must exceed 95%"),
    ("rt_raw",   "range",         0.01, 5000,  "warning",  "Deep resistivity 0.01-5000 Ω·m"),
    ("rhob_raw", "range",         1.50, 3.00,  "critical", "Bulk density 1.5-3.0 g/cc"),
    ("nphi_raw", "range",        -0.15, 0.60,  "warning",  "Neutron porosity -0.15 to 0.60"),
    ("dt_raw",   "range",         40,   200,   "warning",  "Sonic DT 40-200 μs/ft"),
    ("cali_raw", "range",          4,    18,   "warning",  "Caliper 4-18 in"),
    ("md",       "monotonic",    None, None,   "critical", "Depth must be strictly increasing"),
    ("gr_raw",   "spike_detect",  None, None,  "warning",  "Spike detection: z-score > 3.5 on 11-sample window"),
    ("rhob_raw", "spike_detect",  None, None,  "warning",  "Density spike: discontinuity > 0.2 g/cc in 1 sample"),
]


def _get_zone(md: float) -> tuple:
    for z in _ZONES:
        if z[1] <= md < z[2]:
            return z
    return _ZONES[-1]


def _gen_log_samples(well_id: str, depth_start: float, depth_end: float, seed: int,
                     has_dt: bool = True, add_spikes: bool = True,
                     status: str = "raw") -> list:
    rng = random.Random(seed)

    mds = []
    md = depth_start
    while md <= depth_end:
        mds.append(round(md, 1))
        md += 2.0

    n = len(mds)

    # Choose spike positions per curve
    spike_positions = {}
    if add_spikes:
        for curve in ["gr", "rt", "rhob", "nphi", "dt"]:
            n_spikes = rng.randint(3, 7)
            spike_positions[curve] = set(rng.sample(range(n), min(n_spikes, n)))

    # Choose gap positions
    gap_ranges = {}
    for curve in ["gr", "rt", "rhob", "nphi"]:
        gaps = []
        n_gaps = rng.randint(1, 3)
        for _ in range(n_gaps):
            start_idx = rng.randint(50, n - 50)
            length = rng.randint(3, 15)
            gaps.append((start_idx, start_idx + length))
        gap_ranges[curve] = gaps

    rows = []
    for i, md in enumerate(mds):
        z = _get_zone(md)
        (zname, ztop, zbase, gr_mu, gr_sig, logrt_mu, logrt_sig,
         rhob_mu, rhob_sig, nphi_mu, nphi_sig, dt_mu, dt_sig, ztype, pef_mu, sp_mu) = z

        # Trend: subtle gradual change within zone
        frac = (md - ztop) / max(zbase - ztop, 1)
        trend_gr   = gr_mu   + frac * 2
        trend_rhob = rhob_mu + frac * 0.005

        gr_raw   = max(0.0,  round(trend_gr   + rng.gauss(0, gr_sig),   2))
        rt_raw   = round(max(0.01, 10 ** (logrt_mu + rng.gauss(0, logrt_sig))), 4)
        rxo_raw  = round(max(0.01, rt_raw * rng.uniform(0.4, 1.8)), 4)
        rhob_raw = round(max(1.50, min(3.0, trend_rhob + rng.gauss(0, rhob_sig))), 4)
        nphi_raw = round(max(-0.05, min(0.60, nphi_mu + rng.gauss(0, nphi_sig))), 4)
        dt_raw   = round(max(40.0, min(200.0, dt_mu + rng.gauss(0, dt_sig))), 2) if has_dt else None
        cali_raw = round(max(4.0, min(18.0, 8.5 + rng.gauss(0, 0.4))), 3)
        sp_raw   = round(sp_mu + rng.gauss(0, 4), 2)
        pef_raw  = round(max(0.1, pef_mu + rng.gauss(0, 0.2)), 3)

        # QC flags
        gr_qc = rt_qc = rhob_qc = nphi_qc = dt_qc = 0

        # Apply spikes
        if add_spikes:
            if i in spike_positions.get("gr",   set()):
                gr_raw *= rng.choice([3.5, -0.3])
                gr_raw = max(0, round(gr_raw, 2))
                gr_qc = 1
            if i in spike_positions.get("rt",   set()):
                rt_raw *= rng.choice([15.0, 0.05])
                rt_raw = max(0.01, round(rt_raw, 4))
                rt_qc = 1
            if i in spike_positions.get("rhob", set()):
                rhob_raw += rng.choice([0.35, -0.35])
                rhob_raw = round(max(1.0, min(3.5, rhob_raw)), 4)
                rhob_qc = 1
            if i in spike_positions.get("nphi", set()):
                nphi_raw += rng.choice([0.25, -0.25])
                nphi_raw = round(max(-0.1, min(0.65, nphi_raw)), 4)
                nphi_qc = 1
            if has_dt and i in spike_positions.get("dt", set()):
                dt_raw += rng.choice([80.0, -40.0]) if dt_raw else 0
                if dt_raw: dt_raw = round(max(30, min(250, dt_raw)), 2)
                dt_qc = 1

        # Apply gaps (set to None)
        for curve, gaps in gap_ranges.items():
            for (gs, ge) in gaps:
                if gs <= i <= ge:
                    if curve == "gr":   gr_raw = None;   gr_qc = 3
                    if curve == "rt":   rt_raw = None;   rt_qc = 3
                    if curve == "rhob": rhob_raw = None; rhob_qc = 3
                    if curve == "nphi": nphi_raw = None; nphi_qc = 3

        # Range violations
        if gr_raw is not None and (gr_raw < 0 or gr_raw > 250):   gr_qc = max(gr_qc, 2)
        if rhob_raw is not None and (rhob_raw < 1.5 or rhob_raw > 3.0): rhob_qc = max(rhob_qc, 2)
        if nphi_raw is not None and (nphi_raw < -0.15 or nphi_raw > 0.60): nphi_qc = max(nphi_qc, 2)

        # Corrected curves (for processed wells)
        gr_c = rt_c = rhob_c = nphi_c = dt_c = None
        vcl = phi_total = phi_eff = sw = None

        if status in ("corrected", "gold"):
            # Corrected = spike removed + small env correction
            gr_c   = max(0.0, round((gr_raw   if gr_raw   is not None else trend_gr)   + rng.gauss(0, 0.5), 2))
            rt_c   = round(max(0.01, (rt_raw   if rt_raw   is not None else 10**logrt_mu) * rng.uniform(0.97, 1.03)), 4)
            rhob_c = round(max(1.50, min(2.95, (rhob_raw if rhob_raw is not None else trend_rhob) + rng.gauss(0, 0.005))), 4)
            nphi_c = round(max(-0.05, min(0.58, (nphi_raw if nphi_raw is not None else nphi_mu) + rng.gauss(0, 0.003))), 4)
            dt_c   = (round(max(40.0, min(200.0, (dt_raw if dt_raw else dt_mu) + rng.gauss(0, 0.5))), 2)
                      if has_dt else round(dt_mu + rng.gauss(0, 2.0), 2))  # synthetic for missing DT

        if status == "gold":
            GR_MIN, GR_MAX = 20.0, 120.0
            vcl_ = max(0.0, min(1.0, (gr_c - GR_MIN) / (GR_MAX - GR_MIN)))
            RHOB_MA, RHOB_FL = 2.65, 1.0
            phi_t = max(0.0, min(0.5, (RHOB_MA - rhob_c) / (RHOB_MA - RHOB_FL)))
            phi_e = max(0.0, phi_t * (1.0 - vcl_))
            # Simplified Archie: Sw = sqrt(Rw / (phi_eff^2 * RT))
            Rw = 0.05
            if phi_e > 0.02 and rt_c and rt_c > 0:
                sw_ = min(1.0, max(0.0, math.sqrt(Rw / (phi_e ** 2 * rt_c))))
            else:
                sw_ = 1.0
            vcl       = round(vcl_, 4)
            phi_total = round(phi_t, 4)
            phi_eff   = round(phi_e, 4)
            sw        = round(sw_, 4)

        rows.append((
            well_id, md,
            gr_raw, rt_raw, rxo_raw, rhob_raw, nphi_raw, dt_raw, cali_raw, sp_raw, pef_raw,
            gr_qc, rt_qc, rhob_qc, nphi_qc, dt_qc,
            gr_c, rt_c, rhob_c, nphi_c, dt_c,
            vcl, phi_total, phi_eff, sw,
        ))
    return rows


def _compute_curve_quality(well_id: str, rows: list, has_dt: bool) -> list:
    """Compute per-curve quality metrics from the generated data."""
    curves = {
        "gr_raw":   [r[2]  for r in rows],
        "rt_raw":   [r[3]  for r in rows],
        "rhob_raw": [r[5]  for r in rows],
        "nphi_raw": [r[6]  for r in rows],
        "dt_raw":   [r[7]  for r in rows] if has_dt else [],
    }
    qc_flags = {
        "gr_raw":   [r[11] for r in rows],
        "rt_raw":   [r[12] for r in rows],
        "rhob_raw": [r[13] for r in rows],
        "nphi_raw": [r[14] for r in rows],
        "dt_raw":   [r[15] for r in rows] if has_dt else [],
    }
    results = []
    for name, vals in curves.items():
        if not vals:
            continue
        n = len(vals)
        non_null = sum(1 for v in vals if v is not None)
        coverage = round(non_null / n * 100, 1) if n > 0 else 0.0
        flags = qc_flags.get(name, [])
        spikes = sum(1 for f in flags if f == 1)
        gaps   = sum(1 for f in flags if f == 3)
        q = int(coverage * 0.6 + (1 - spikes / max(n, 1) * 10) * 25 + (1 - gaps / max(n, 1) * 20) * 15)
        q = max(0, min(100, q))
        results.append((well_id, name, coverage, coverage, spikes, gaps, q))
    return results


def _build_formation_tops(well_id: str) -> list:
    """Generate formation top records for a well."""
    tops = []
    lithology_map = {
        "shale":    "Dark grey organic shale, high gamma, low resistivity",
        "sand":     "Mixed fluvial sandstone and siltstone, moderate pay",
        "carbonate":"Tight limestone/dolomite, very low GR, high resistivity",
        "reservoir":"Clean porous sandstone, hydrocarbon bearing, low GR",
        "fluvial":  "Fluvial channel sand and overbank shale alternation",
    }
    prev_base = None
    for z in _ZONES:
        name, top, base, *_, ztype, _, _ = z
        if prev_base is not None:
            # small per-well depth variation
            offset = (hash(well_id + name) % 100) - 50
        else:
            offset = 0
        adj_top  = top  + offset
        adj_base = base + offset
        tops.append((well_id, name, float(adj_top), float(adj_base), ztype, lithology_map.get(ztype, "")))
        prev_base = adj_base
    return tops


async def seed_data(conn):
    count = await conn.fetchval("SELECT COUNT(*) FROM las.wells")
    if count and count > 0:
        print("LAS data already seeded, skipping.")
        return

    import json as _json

    # ── Insert QC rules ──────────────────────────────────────────────────────
    for (curve, rtype, tmin, tmax, sev, desc) in _QC_RULES:
        await conn.execute(
            "INSERT INTO las.qc_rules (curve_name, rule_type, threshold_min, threshold_max, severity, description) "
            "VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
            curve, rtype, tmin, tmax, sev, desc
        )

    # ── Insert recipes ───────────────────────────────────────────────────────
    for r in _RECIPES:
        await conn.execute(
            "INSERT INTO las.processing_recipes (recipe_id,name,description,version,category,steps) "
            "VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
            r["recipe_id"], r["name"], r["description"], r["version"], r["category"],
            _json.dumps(r["steps"])
        )

    # ── Insert wells, logs, formation tops, curve quality ───────────────────
    INSERT_WELL = (
        "INSERT INTO las.wells "
        "(well_id,well_name,field_name,basin,county,state,api_number,lat,lon,"
        " kb_elevation_ft,total_depth_ft,spud_date,well_type,status,quality_score,curve_count,notes) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17) ON CONFLICT DO NOTHING"
    )
    INSERT_TOP = (
        "INSERT INTO las.formation_tops (well_id,formation_name,top_md,base_md,zone_type,lithology_desc) "
        "VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING"
    )
    INSERT_LOG = (
        "INSERT INTO las.depth_logs "
        "(well_id,md,gr_raw,rt_raw,rxo_raw,rhob_raw,nphi_raw,dt_raw,cali_raw,sp_raw,pef_raw,"
        " gr_qc,rt_qc,rhob_qc,nphi_qc,dt_qc,"
        " gr_c,rt_c,rhob_c,nphi_c,dt_c,vcl,phi_total,phi_eff,sw) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,"
        "$17,$18,$19,$20,$21,$22,$23,$24,$25) ON CONFLICT DO NOTHING"
    )
    INSERT_CQ = (
        "INSERT INTO las.curve_quality (well_id,curve_name,coverage_pct,in_range_pct,spike_count,gap_count,quality_score) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING"
    )

    well_configs = [
        # well_id, seed, has_dt, add_spikes
        ("BAKER-001",   42,  True,  True),
        ("BAKER-002",   77,  True,  True),
        ("CONOCO-7H",   13,  False, True),
        ("MARATHON-15X",99,  True,  True),
        ("SHELL-3D",    55,  True,  False),
        ("PIONEER-22S", 31,  True,  True),
    ]

    for wdata in _WELLS:
        (wid, wname, field, basin, county, state, api, lat, lon, kb, td, spud,
         wtype, status, qscore, notes) = wdata
        spud_date = datetime.date.fromisoformat(spud) if spud else None
        curve_count = 9 if not wid.startswith("CONOCO") else 8
        await conn.execute(INSERT_WELL,
            wid, wname, field, basin, county, state, api, lat, lon, kb, td,
            spud_date, wtype, status, qscore, curve_count, notes
        )

        # Formation tops
        for top_row in _build_formation_tops(wid):
            await conn.execute(INSERT_TOP, *top_row)

    # Depth logs (bulk insert per well)
    for (wid, seed, has_dt, add_spikes) in well_configs:
        well_meta = next(w for w in _WELLS if w[0] == wid)
        status = well_meta[13]
        rows = _gen_log_samples(wid, 5000.0, 10000.0, seed, has_dt=has_dt,
                                add_spikes=add_spikes, status=status)
        # Batch insert
        BATCH = 500
        for start in range(0, len(rows), BATCH):
            await conn.executemany(INSERT_LOG, rows[start:start + BATCH])

        # Curve quality
        cq_rows = _compute_curve_quality(wid, rows, has_dt)
        for cq in cq_rows:
            await conn.execute(INSERT_CQ, *cq)

    # ── Seed some anomaly records ────────────────────────────────────────────
    anomalies = [
        ("BAKER-002",   "rhob_raw", 7520.0, 7540.0, "washout",     "warning",  None,
         "Caliper > 12in suggests borehole washout; density unreliable"),
        ("BAKER-002",   "nphi_raw", 7520.0, 7540.0, "washout",     "warning",  None,
         "Washout-induced apparent porosity increase"),
        ("CONOCO-7H",   "dt_raw",   5000.0, 10000.0,"curve_missing","critical", None,
         "No DT acquisition — synthetic sonic required for geomechanics"),
        ("MARATHON-15X","gr_raw",   8100.0, 8104.0,  "spike",       "warning",  421.5,
         "GR spike 421 API at 8100 ft — likely tool noise during connection"),
        ("MARATHON-15X","rt_raw",   6804.0, 6812.0,  "spike",       "warning",  0.003,
         "Resistivity dropout to 0.003 Ω·m — probable mud invasion artifact"),
        ("PIONEER-22S", "rhob_raw", 6850.0, 6920.0,  "karst",       "warning",  None,
         "Karst-related density anomaly in Todilto carbonate"),
    ]
    for a in anomalies:
        await conn.execute(
            "INSERT INTO las.anomalies (well_id,curve_name,depth_start,depth_end,anomaly_type,severity,value,description) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT DO NOTHING", *a
        )

    # ── Seed a couple of processing run history records ──────────────────────
    runs = [
        ("RUN-001", "BAKER-001",   "STD-PETRO-V1",  "complete",
         datetime.datetime(2024, 3, 10, 8, 0),
         datetime.datetime(2024, 3, 10, 8, 4),
         {"samples": 2501, "spikes_corrected": 5, "gaps_filled": 8, "phi_mean": 0.12, "sw_mean": 0.42}),
        ("RUN-002", "SHELL-3D",    "HIFI-RSVR-V1",  "complete",
         datetime.datetime(2024, 5, 18, 14, 0),
         datetime.datetime(2024, 5, 18, 14, 9),
         {"samples": 2501, "spikes_corrected": 0, "gaps_filled": 2, "phi_mean": 0.14, "sw_mean": 0.38}),
        ("RUN-003", "BAKER-002",   "STD-PETRO-V1",  "complete",
         datetime.datetime(2024, 4, 2, 9, 30),
         datetime.datetime(2024, 4, 2, 9, 33),
         {"samples": 2501, "spikes_corrected": 12, "gaps_filled": 15, "phi_mean": 0.10, "sw_mean": 0.51}),
        ("RUN-004", "MARATHON-15X","STD-PETRO-V1",  "pending",
         None, None, {}),
    ]
    for (rid, wid, recipe, status, ts_start, ts_end, metrics) in runs:
        await conn.execute(
            "INSERT INTO las.processing_runs (run_id,well_id,recipe_id,status,started_ts,completed_ts,metrics) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING",
            rid, wid, recipe, status, ts_start, ts_end, _json.dumps(metrics)
        )

    print(f"LAS seed data inserted: {len(_WELLS)} wells, {len(_RECIPES)} recipes.")

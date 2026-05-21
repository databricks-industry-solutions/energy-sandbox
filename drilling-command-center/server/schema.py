import math
import random
import datetime

CREATE_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS las;

CREATE SEQUENCE IF NOT EXISTS las.seq_qc_rules START 1;
CREATE SEQUENCE IF NOT EXISTS las.seq_anomalies START 1;
CREATE SEQUENCE IF NOT EXISTS las.seq_journal START 1;
CREATE SEQUENCE IF NOT EXISTS las.seq_alerts START 1;

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
    rule_id     INTEGER PRIMARY KEY DEFAULT nextval('las.seq_qc_rules'),
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
    steps       JSON,
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
    metrics     JSON,
    created_by  VARCHAR(64) DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS las.anomalies (
    id          BIGINT PRIMARY KEY DEFAULT nextval('las.seq_anomalies'),
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

-- ─────────── Drilling Command Center extensions ─────────────────────────────
CREATE TABLE IF NOT EXISTS las.well_economics (
    well_id         VARCHAR(64) PRIMARY KEY,
    capex_musd      DOUBLE PRECISION,
    opex_musd_yr    DOUBLE PRECISION,
    peak_rate_bopd  DOUBLE PRECISION,
    decline_pct_yr  DOUBLE PRECISION,
    wti_break_even  DOUBLE PRECISION,
    npv10_musd      DOUBLE PRECISION,
    irr_pct         DOUBLE PRECISION,
    payback_years   DOUBLE PRECISION,
    co2_tonnes_yr   DOUBLE PRECISION,
    updated_ts      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS las.wti_prices (
    price_date      DATE PRIMARY KEY,
    price_usd       DOUBLE PRECISION NOT NULL,
    source          VARCHAR(32) DEFAULT 'FRED'
);

CREATE TABLE IF NOT EXISTS las.drilling_operations (
    well_id                 VARCHAR(64) PRIMARY KEY,
    rig_name                VARCHAR(64),
    rig_contractor          VARCHAR(64),
    rig_status              VARCHAR(32),
    days_on_well            INTEGER,
    npt_hours_last_30d      DOUBLE PRECISION,
    casing_strings_set      INTEGER,
    drilling_phase          VARCHAR(32),
    current_md_ft           DOUBLE PRECISION,
    rop_ft_per_hr           DOUBLE PRECISION,
    mud_weight_ppg          DOUBLE PRECISION,
    last_incident_date      DATE,
    last_incident_severity  VARCHAR(16),
    last_incident_desc      VARCHAR(256),
    supply_chain_status     VARCHAR(32),
    days_to_next_casing     INTEGER,
    esp_health_pct          INTEGER,
    mud_pump_health_pct     INTEGER,
    updated_ts              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS las.reservoir_simulated (
    well_id                 VARCHAR(64) PRIMARY KEY,
    formation_name          VARCHAR(64),
    avg_porosity_frac       DOUBLE PRECISION,
    avg_permeability_md     DOUBLE PRECISION,
    avg_oil_saturation      DOUBLE PRECISION,
    avg_water_saturation    DOUBLE PRECISION,
    net_pay_ft              DOUBLE PRECISION,
    original_oil_in_place_mmbbl DOUBLE PRECISION,
    initial_pressure_psi    DOUBLE PRECISION,
    reservoir_temp_f        DOUBLE PRECISION,
    reservoir_depth_ft      DOUBLE PRECISION,
    analog_well_id          VARCHAR(64),
    analog_field            VARCHAR(64),
    updated_ts              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS las.drilling_journal (
    entry_id        BIGINT PRIMARY KEY DEFAULT nextval('las.seq_journal'),
    well_id         VARCHAR(64),
    author          VARCHAR(64),
    depth_md        DOUBLE PRECISION,
    note            TEXT,
    ai_summary      TEXT,
    entered_ts      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journal_well ON las.drilling_journal (well_id, entered_ts DESC);

CREATE TABLE IF NOT EXISTS las.drilling_alerts (
    alert_id        BIGINT PRIMARY KEY DEFAULT nextval('las.seq_alerts'),
    well_id         VARCHAR(64),
    severity        VARCHAR(16),
    category        VARCHAR(32),
    title           VARCHAR(128),
    detail          TEXT,
    depth_md        DOUBLE PRECISION,
    ack_by          VARCHAR(64),
    ack_ts          TIMESTAMPTZ,
    raised_ts       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_well ON las.drilling_alerts (well_id);

CREATE TABLE IF NOT EXISTS las.persona_grants (
    persona         VARCHAR(32) PRIMARY KEY,
    label           VARCHAR(64),
    allowed_fields  TEXT,
    row_filter      TEXT,
    description     TEXT
);
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

    # ── Seed personas for governance demo ────────────────────────────────────
    personas = [
        ("operator",       "Drilling Operator",
         "all",
         None,
         "Full read on operational data; sees own operator's wells including PII/DRM tags"),
        ("analyst",        "Reservoir Analyst",
         "well_name,basin,field_name,lat,lon,kb_elevation_ft,total_depth_ft,spud_date,status,quality_score",
         None,
         "Read on geological + petrophysical data; no operator PII, no raw economics"),
        ("external_partner","External Partner (JV)",
         "well_name,basin,field_name,status",
         "status IN ('gold','corrected')",
         "Joint-venture view — status-filtered, coarse metadata only, no economics, no raw logs"),
        ("compliance",     "Compliance / Legal",
         "well_id,well_name,status,notes",
         None,
         "Legal tag + entitlement auditing; sees governance metadata across all wells"),
    ]
    for p in personas:
        await conn.execute(
            "INSERT INTO las.persona_grants (persona, label, allowed_fields, row_filter, description) "
            "VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
            *p
        )

    # ── Simulated drilling operations (rig, NPT, supply chain) for NA fleet ────
    drilling_ops = [
        # well_id,        rig,                contractor,    status,       days, npt_30d, csg, phase,     md,    rop, mud,  inc_date,    sev,        incident, supply,   next_csg, esp, pump
        ("BAKER-001",     "Patterson 314",    "Patterson",   "drilling",     42, 36.5,    3, "production", 9450, 18.4, 9.6, "2026-04-22","minor",    "Hole pack-off at 8120 ft, cleared in 4 hr", "on schedule",     6,  91, 88),
        ("BAKER-002",     "Patterson 207",    "Patterson",   "drilling",     58, 72.1,    3, "production", 9780, 14.1, 9.8, "2026-05-11","moderate", "Lost circulation in Brushy Basin shale",  "casing delayed", 12,  85, 82),
        ("CONOCO-7H",     "Helmerich H&P 412","H&P",         "logging",      71, 28.0,    4, "evaluation", 9800, 0.0, 10.2, "2026-03-30","minor",    "Twist-off recovered with overshot",        "on schedule",     0,  93, 90),
        ("MARATHON-15X",  "Independence 88",  "Independence","spud",          5,  2.5,    1, "surface",     940, 96.2, 8.8, None,         None,       None,                                       "on schedule",     3,  95, 96),
        ("SHELL-3D",      "Nabors B-12",      "Nabors",      "completion",  108,  6.0,    4, "completion",10000,  0.0, 9.4, "2026-02-14","minor",    "Cement bond log re-run on lateral",        "on schedule",     0,  98, 95),
        ("PIONEER-22S",   "Patterson 119",    "Patterson",   "drilling",     34, 41.8,    2, "intermediate",6200,16.7, 10.0,"2026-05-02","major",    "BHA failed at 5840 ft; tripped out clean", "BHA delayed",     8,  74, 78),
    ]
    for r in drilling_ops:
        inc_date = None
        try:
            inc_date = datetime.date.fromisoformat(r[11]) if r[11] else None
        except Exception:
            pass
        await conn.execute(
            "INSERT INTO las.drilling_operations "
            "(well_id, rig_name, rig_contractor, rig_status, days_on_well, npt_hours_last_30d, "
            " casing_strings_set, drilling_phase, current_md_ft, rop_ft_per_hr, mud_weight_ppg, "
            " last_incident_date, last_incident_severity, last_incident_desc, supply_chain_status, "
            " days_to_next_casing, esp_health_pct, mud_pump_health_pct) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18) "
            "ON CONFLICT (well_id) DO UPDATE SET "
            "rig_status=EXCLUDED.rig_status, days_on_well=EXCLUDED.days_on_well, "
            "npt_hours_last_30d=EXCLUDED.npt_hours_last_30d, current_md_ft=EXCLUDED.current_md_ft, "
            "rop_ft_per_hr=EXCLUDED.rop_ft_per_hr, mud_weight_ppg=EXCLUDED.mud_weight_ppg, "
            "last_incident_date=EXCLUDED.last_incident_date, last_incident_desc=EXCLUDED.last_incident_desc, "
            "supply_chain_status=EXCLUDED.supply_chain_status, esp_health_pct=EXCLUDED.esp_health_pct",
            r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10],
            inc_date, r[12], r[13], r[14], r[15], r[16], r[17],
        )

    # ── Simulated reservoir metrics for NA wells, with ADME analog references ──
    # Each NA well is paired with an ADME analog (Norwegian Continental Shelf,
    # Blocks 15/9 and 34/10) based on formation/reservoir similarity. The
    # petrophysics values are simulated to match the analog's profile so the
    # Supervisor's Petrophysics specialist has clean UC-shape data to reason over.
    reservoir_sim = [
        # well_id,         formation,                phi,   k_md, So,   Sw,   net_pay, OOIP, P_psi, T_F, depth_ft, analog,        analog_field
        ("BAKER-001",     "Mancos / Westwater",      0.182, 145.0, 0.74, 0.22, 78,  18.4, 3200, 168, 9450, "15/9-F-1 A",   "Block 15/9"),
        ("BAKER-002",     "Mancos / Brushy Basin",   0.155, 88.0,  0.71, 0.25, 62,  14.2, 3260, 172, 9780, "15/9-F-14",    "Block 15/9"),
        ("CONOCO-7H",     "Lewis Shale / Almond",    0.142, 22.0,  0.66, 0.30, 95,  21.3, 4150, 184, 9800, "34/10-A-1 H",  "Block 34/10"),
        ("MARATHON-15X",  "Wolfcamp A",              0.084, 0.18,  0.78, 0.20, 110, 28.0, 4900, 192, 9800, "34/10-7",      "Block 34/10"),
        ("SHELL-3D",      "Woodbine / Tuscaloosa",   0.215, 320.0, 0.82, 0.16, 65,  32.5, 4400, 198, 10000,"15/9-F-11",    "Block 15/9"),
        ("PIONEER-22S",   "Edwards Lime",            0.108, 2.8,   0.70, 0.27, 84,  19.7, 4250, 188, 9800, "34/10-B-1 H",  "Block 34/10"),
    ]
    for r in reservoir_sim:
        await conn.execute(
            "INSERT INTO las.reservoir_simulated "
            "(well_id, formation_name, avg_porosity_frac, avg_permeability_md, avg_oil_saturation, "
            " avg_water_saturation, net_pay_ft, original_oil_in_place_mmbbl, initial_pressure_psi, "
            " reservoir_temp_f, reservoir_depth_ft, analog_well_id, analog_field) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) "
            "ON CONFLICT (well_id) DO UPDATE SET "
            "avg_porosity_frac=EXCLUDED.avg_porosity_frac, avg_permeability_md=EXCLUDED.avg_permeability_md, "
            "avg_oil_saturation=EXCLUDED.avg_oil_saturation, analog_well_id=EXCLUDED.analog_well_id",
            *r,
        )

    # ── Operator economics (was previously seeded inside seed_osdu_wells, but
    # that now runs as a background task — moving here so Economics tab is
    # populated immediately at startup) ─────────────────────────────────────────
    operator_econ = [
        # well_id,        capex,opex, peak, decl, BE, NPV10, IRR, payback, CO2
        ("BAKER-001",     58.0, 4.1, 1800, 18, 42, 28.4, 32.0, 2.8, 2100),
        ("BAKER-002",     52.0, 3.8, 1500, 20, 48, 14.2, 19.0, 3.8, 1900),
        ("CONOCO-7H",     72.0, 5.2, 3200, 28, 52, 42.1, 38.0, 2.2, 3400),
        ("MARATHON-15X",  48.0, 3.5, 1200, 25, 58,  8.6, 14.0, 4.5, 1700),
        ("SHELL-3D",      65.0, 4.8, 2100, 15, 38, 55.8, 44.0, 2.1, 2400),
        ("PIONEER-22S",   44.0, 3.2, 1400, 22, 51, 11.2, 17.0, 4.2, 1800),
    ]
    for (wid, capex, opex, rate, decl, be, npv, irr, pb, co2) in operator_econ:
        await conn.execute(
            "INSERT INTO las.well_economics (well_id, capex_musd, opex_musd_yr, peak_rate_bopd, "
            "decline_pct_yr, wti_break_even, npv10_musd, irr_pct, payback_years, co2_tonnes_yr) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT (well_id) DO UPDATE SET "
            "capex_musd=EXCLUDED.capex_musd, opex_musd_yr=EXCLUDED.opex_musd_yr, "
            "peak_rate_bopd=EXCLUDED.peak_rate_bopd, decline_pct_yr=EXCLUDED.decline_pct_yr, "
            "wti_break_even=EXCLUDED.wti_break_even, npv10_musd=EXCLUDED.npv10_musd, "
            "irr_pct=EXCLUDED.irr_pct, payback_years=EXCLUDED.payback_years, "
            "co2_tonnes_yr=EXCLUDED.co2_tonnes_yr",
            wid, capex, opex, rate, decl, be, npv, irr, pb, co2,
        )

    # ── Seed a minimal WTI price history so the Economics tab has something
    # to render before the (slow) FRED Marketplace fetch finishes in the
    # background. Generates 120 days of synthetic prices ~$78 ± $5. ─────────────
    import math, random
    rng = random.Random(20260518)
    today = datetime.date.today()
    for i in range(120, -1, -1):
        d = today - datetime.timedelta(days=i)
        p = 78 + 4 * math.sin(i / 7.0) + 2 * math.cos(i / 21.0) + (rng.random() - 0.5) * 4
        p = max(45.0, min(120.0, round(p, 2)))
        await conn.execute(
            "INSERT INTO las.wti_prices (price_date, price_usd, source) "
            "VALUES ($1, $2, 'synthetic-bootstrap') ON CONFLICT (price_date) DO NOTHING",
            d, p,
        )

    print(f"LAS seed data inserted: {len(_WELLS)} wells, {len(_RECIPES)} recipes, {len(personas)} personas, "
          f"{len(drilling_ops)} drilling ops, {len(reservoir_sim)} reservoir sims, "
          f"{len(operator_econ)} economics, 121 WTI bootstrap prices.")


async def seed_osdu_wells(conn):
    """Append OSDU-sourced wells to las.wells (idempotent). Falls back silently
    if OSDU catalog is unreachable — app still renders with hardcoded wells."""
    try:
        from .osdu_live import fetch_osdu_wells
    except Exception as e:
        print(f"OSDU seeder import failed: {e}")
        return

    osdu_wells = fetch_osdu_wells()
    if not osdu_wells:
        print("No OSDU wells returned (auth / catalog access missing?); skipping.")
        return

    INSERT_WELL = (
        "INSERT INTO las.wells "
        "(well_id,well_name,field_name,basin,county,state,api_number,lat,lon,"
        " kb_elevation_ft,total_depth_ft,spud_date,well_type,status,quality_score,curve_count,notes) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17) "
        "ON CONFLICT (well_id) DO UPDATE SET "
        "well_name=EXCLUDED.well_name, field_name=EXCLUDED.field_name, "
        "status=EXCLUDED.status, notes=EXCLUDED.notes"
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

    inserted = 0
    for w in osdu_wells:
        spud = None
        try:
            spud = datetime.date.fromisoformat(w["spud_date"]) if w.get("spud_date") else None
        except Exception:
            pass
        await conn.execute(INSERT_WELL,
            w["well_id"], w["well_name"], w.get("field_name"), w.get("basin"),
            w.get("county"), w.get("state"), w.get("api_number"),
            w.get("lat"), w.get("lon"),
            w.get("kb_elevation_ft") or 80.0, w.get("total_depth_ft") or 10000.0,
            spud, w.get("well_type") or "deviated", w.get("status") or "corrected",
            w.get("quality_score") or 70, 9, w.get("notes") or "",
        )

        # Formation tops from canned zones
        for top_row in _build_formation_tops(w["well_id"]):
            await conn.execute(INSERT_TOP, *top_row)

        # Synthetic logs using OSDU TD — scaled to the well's depth
        td_ft = float(w.get("total_depth_ft") or 10000.0)
        depth_start = max(1000.0, td_ft - 5000.0)
        depth_end = td_ft
        seed_val = abs(hash(w["well_id"])) % 10000
        rows = _gen_log_samples(
            w["well_id"], depth_start, depth_end, seed_val,
            has_dt=True, add_spikes=True, status=w.get("status") or "corrected",
        )
        BATCH = 500
        for start in range(0, len(rows), BATCH):
            await conn.executemany(INSERT_LOG, rows[start:start + BATCH])

        cq_rows = _compute_curve_quality(w["well_id"], rows, True)
        for cq in cq_rows:
            await conn.execute(INSERT_CQ, *cq)

        # Seed simple economics row (stub, updated later by /api/economics/recalc)
        if (w.get("drilling_result") or "").lower() == "producer":
            await conn.execute(
                "INSERT INTO las.well_economics (well_id, capex_musd, opex_musd_yr, peak_rate_bopd, "
                "decline_pct_yr, wti_break_even, npv10_musd, irr_pct, payback_years, co2_tonnes_yr) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT DO NOTHING",
                w["well_id"], 42.0, 3.2, 2400.0, 22.0, 48.0, 18.5, 27.0, 3.1, 1800.0,
            )

        inserted += 1

    print(f"OSDU wells seeded: {inserted}")
    # NA operator economics is seeded in seed_data() at startup (so the
    # Economics tab is populated immediately, not after this background task).


async def seed_wti_prices(conn):
    """Pull WTI spot prices from FRED and seed las.wti_prices."""
    try:
        from .prices import fetch_wti_prices
    except Exception as e:
        print(f"prices module import failed: {e}")
        return
    prices = fetch_wti_prices(years_back=3)
    if not prices:
        print("WTI fetch returned 0 rows; skipping.")
        return
    await conn.executemany(
        "INSERT INTO las.wti_prices (price_date, price_usd, source) VALUES ($1,$2,'FRED') "
        "ON CONFLICT (price_date) DO NOTHING",
        [(d, p) for (d, p) in prices],
    )
    print(f"WTI prices seeded: {len(prices)} rows (latest ${prices[-1][1]:.2f} on {prices[-1][0]})")

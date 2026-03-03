import json

# SQLite-compatible DDL (no SERIAL, no JSONB, no TIMESTAMPTZ, no FK deferral)
CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scenarios (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    deck_id TEXT NOT NULL,
    description TEXT DEFAULT '',
    config  TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id          TEXT PRIMARY KEY,
    scenario_id INTEGER,
    status      TEXT NOT NULL DEFAULT 'PENDING',
    deck_path   TEXT DEFAULT '',
    output_dir  TEXT DEFAULT '',
    progress    INTEGER DEFAULT 0,
    current_timestep REAL DEFAULT 0,
    total_timesteps  INTEGER DEFAULT 0,
    log_tail    TEXT DEFAULT '',
    started_at  TEXT,
    finished_at TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS economics_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT,
    scenario_id     INTEGER DEFAULT 0,
    oil_price       REAL DEFAULT 75.0,
    gas_price       REAL DEFAULT 2.80,
    discount_rate   REAL DEFAULT 0.10,
    opex_per_boe    REAL DEFAULT 8.50,
    capex_per_well  REAL DEFAULT 8000000,
    npv_usd         REAL,
    irr             REAL,
    payback_year    INTEGER,
    cashflows       TEXT DEFAULT '[]',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_operations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    operations  TEXT DEFAULT '[]',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_costs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    costs       TEXT DEFAULT '{}',
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS delta_sharing_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    direction   TEXT NOT NULL DEFAULT 'OUTBOUND',
    sync_data   TEXT DEFAULT '{}',
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

_SCENARIOS = [
    {
        "name": "Norne Base Case",
        "deck_id": "norne_base",
        "description": "Norne field primary depletion (North Sea). "
                       "4 producers: B-2H, D-1H, E-3H, D-2H. "
                       "Initial pressure 360 bar, 20×10×5 representative grid. "
                       "Reference: NORNE_ATW2013 benchmark dataset.",
        "config": {
            "wells": [
                {"name": "B-2H", "type": "PROD", "i": 5,  "j": 7, "bhp": 200},
                {"name": "D-1H", "type": "PROD", "i": 9,  "j": 4, "bhp": 200},
                {"name": "E-3H", "type": "PROD", "i": 5,  "j": 3, "bhp": 200},
                {"name": "D-2H", "type": "PROD", "i": 15, "j": 3, "bhp": 200},
            ],
            "start_date": "1997-11-06",
            "end_date": "2006-12-01",
            "timestep_days": 91,
            "grid": {"ni": 20, "nj": 10, "nk": 5},
            "initial_pressure_bar": 360,
            "porosity": 0.25,
            "permeability_md": 120,
            "field": "Norne",
            "formation": "Fangst/Ile",
        },
    },
    {
        "name": "Norne Gas Injection",
        "deck_id": "norne_ginj",
        "description": "Norne gas injection scenario. C-4H converts to gas injector "
                       "providing pressure maintenance. Matches historical C-4H injection "
                       "rates from the NORNE_ATW2013 schedule.",
        "config": {
            "wells": [
                {"name": "B-2H", "type": "PROD", "i": 5,  "j": 7, "bhp": 200},
                {"name": "D-1H", "type": "PROD", "i": 9,  "j": 4, "bhp": 200},
                {"name": "E-3H", "type": "PROD", "i": 5,  "j": 3, "bhp": 200},
                {"name": "D-2H", "type": "PROD", "i": 15, "j": 3, "bhp": 200},
                {"name": "C-4H", "type": "INJ",  "i": 15, "j": 7, "rate": 1500},
            ],
            "start_date": "1997-11-06",
            "end_date": "2006-12-01",
            "timestep_days": 91,
            "grid": {"ni": 20, "nj": 10, "nk": 5},
            "initial_pressure_bar": 360,
            "porosity": 0.25,
            "permeability_md": 120,
            "field": "Norne",
            "formation": "Fangst/Ile",
        },
    },
    {
        "name": "Norne Full Field",
        "deck_id": "norne_full",
        "description": "Full Norne field development: B-2H, D-1H, E-3H, D-2H, B-4H "
                       "producers + C-4H gas injector. Represents peak field production "
                       "period 1997–2006.",
        "config": {
            "wells": [
                {"name": "B-2H", "type": "PROD", "i": 5,  "j": 7, "bhp": 200},
                {"name": "D-1H", "type": "PROD", "i": 9,  "j": 4, "bhp": 200},
                {"name": "E-3H", "type": "PROD", "i": 5,  "j": 3, "bhp": 200},
                {"name": "D-2H", "type": "PROD", "i": 15, "j": 3, "bhp": 200},
                {"name": "B-4H", "type": "PROD", "i": 3,  "j": 6, "bhp": 200},
                {"name": "C-4H", "type": "INJ",  "i": 15, "j": 7, "rate": 1500},
            ],
            "start_date": "1997-11-06",
            "end_date": "2006-12-01",
            "timestep_days": 91,
            "grid": {"ni": 20, "nj": 10, "nk": 5},
            "initial_pressure_bar": 360,
            "porosity": 0.25,
            "permeability_md": 120,
            "field": "Norne",
            "formation": "Fangst/Ile",
        },
    },
]


async def seed_data():
    from .db import db
    count = await db.fetchval("SELECT COUNT(*) FROM scenarios")
    if count and count > 0:
        print(f"Scenarios already seeded ({count} rows), skipping.")
        return
    for s in _SCENARIOS:
        await db.execute(
            "INSERT INTO scenarios (name, deck_id, description, config) VALUES (?,?,?,?)",
            s["name"], s["deck_id"], s["description"], json.dumps(s["config"]),
        )
    print(f"Seeded {len(_SCENARIOS)} scenarios.")

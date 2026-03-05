"""
Pipeline Command Center — Static / Mock Data Layer
Midstream oil & gas pipeline command center with digital twin.
"""

from __future__ import annotations

# ── Pipeline Asset Registry ────────────────────────────────────────
ASSETS = [
    {"asset_id": "SEG-01",  "name": "Segment 1 — Gathering Line 16″",      "type": "PIPE_SEGMENT",      "mile_start": 0.0,   "mile_end": 18.5},
    {"asset_id": "SEG-02",  "name": "Segment 2 — Trunk Line 24″",          "type": "PIPE_SEGMENT",      "mile_start": 18.5,  "mile_end": 52.0},
    {"asset_id": "SEG-03",  "name": "Segment 3 — Trunk Line 24″",          "type": "PIPE_SEGMENT",      "mile_start": 52.0,  "mile_end": 87.3},
    {"asset_id": "CS-01",   "name": "Compressor Station Alpha",             "type": "COMPRESSOR",        "mile": 18.5},
    {"asset_id": "CS-02",   "name": "Compressor Station Bravo",             "type": "COMPRESSOR",        "mile": 52.0},
    {"asset_id": "PS-01",   "name": "Pump Station 1 — Booster",             "type": "PUMP_STATION",      "mile": 0.0},
    {"asset_id": "PS-02",   "name": "Pump Station 2 — Mainline",            "type": "PUMP_STATION",      "mile": 52.0},
    {"asset_id": "MET-01",  "name": "Custody Transfer Meter — Inlet",       "type": "METERING",          "mile": 0.0},
    {"asset_id": "MET-02",  "name": "Custody Transfer Meter — Delivery",    "type": "METERING",          "mile": 87.3},
    {"asset_id": "PIG-01",  "name": "Pig Launcher — Inlet",                 "type": "PIG_LAUNCHER",      "mile": 0.0},
    {"asset_id": "PIG-02",  "name": "Pig Receiver — Delivery",              "type": "PIG_RECEIVER",      "mile": 87.3},
    {"asset_id": "VLV-01",  "name": "Block Valve Station 1",                "type": "VALVE_STATION",     "mile": 18.5},
    {"asset_id": "VLV-02",  "name": "Block Valve Station 2",                "type": "VALVE_STATION",     "mile": 52.0},
    {"asset_id": "VLV-03",  "name": "Block Valve Station 3 — Delivery",     "type": "VALVE_STATION",     "mile": 87.3},
    {"asset_id": "RTU-01",  "name": "SCADA RTU — Inlet Terminal",           "type": "RTU",               "mile": 0.0},
    {"asset_id": "RTU-02",  "name": "SCADA RTU — Midpoint",                 "type": "RTU",               "mile": 52.0},
    {"asset_id": "RTU-03",  "name": "SCADA RTU — Delivery Terminal",        "type": "RTU",               "mile": 87.3},
    {"asset_id": "CP-01",   "name": "Cathodic Protection Rectifier Bank",   "type": "CP_SYSTEM",         "mile": 0.0},
]

# ── Sensor Baselines by Asset Type ─────────────────────────────────
SENSOR_DEFS: dict[str, list[dict]] = {
    "PIPE_SEGMENT": [
        {"tag": "PRESS_IN",    "label": "Inlet Pressure",       "unit": "psig",  "base": 1050, "noise": 15},
        {"tag": "PRESS_OUT",   "label": "Outlet Pressure",      "unit": "psig",  "base": 980,  "noise": 15},
        {"tag": "FLOW",        "label": "Flow Rate",             "unit": "bbl/h", "base": 8500, "noise": 120},
        {"tag": "TEMP",        "label": "Temperature",           "unit": "°F",    "base": 105,  "noise": 3},
        {"tag": "CORR_RATE",   "label": "Corrosion Rate",        "unit": "mpy",   "base": 2.1,  "noise": 0.3},
    ],
    "COMPRESSOR": [
        {"tag": "SUCT_PRESS",  "label": "Suction Pressure",     "unit": "psig",  "base": 450,  "noise": 10},
        {"tag": "DISCH_PRESS", "label": "Discharge Pressure",   "unit": "psig",  "base": 1050, "noise": 15},
        {"tag": "VIBRATION",   "label": "Vibration",             "unit": "mm/s",  "base": 3.2,  "noise": 0.4},
        {"tag": "TEMP_BEAR",   "label": "Bearing Temperature",  "unit": "°F",    "base": 165,  "noise": 5},
        {"tag": "RPM",         "label": "Shaft Speed",           "unit": "RPM",   "base": 3600, "noise": 20},
    ],
    "PUMP_STATION": [
        {"tag": "SUCT_PRESS",  "label": "Suction Pressure",     "unit": "psig",  "base": 50,   "noise": 5},
        {"tag": "DISCH_PRESS", "label": "Discharge Pressure",   "unit": "psig",  "base": 1080, "noise": 15},
        {"tag": "FLOW",        "label": "Flow Rate",             "unit": "bbl/h", "base": 8500, "noise": 120},
        {"tag": "CURRENT",     "label": "Motor Current",         "unit": "A",     "base": 280,  "noise": 8},
        {"tag": "VIBRATION",   "label": "Vibration",             "unit": "mm/s",  "base": 2.8,  "noise": 0.3},
        {"tag": "TEMP_BEAR",   "label": "Bearing Temperature",  "unit": "°F",    "base": 155,  "noise": 4},
    ],
    "METERING": [
        {"tag": "FLOW",        "label": "Flow Rate",             "unit": "bbl/h", "base": 8500, "noise": 80},
        {"tag": "TEMP",        "label": "Temperature",           "unit": "°F",    "base": 102,  "noise": 2},
        {"tag": "PRESS",       "label": "Pressure",              "unit": "psig",  "base": 980,  "noise": 10},
        {"tag": "DENSITY",     "label": "Density",               "unit": "lb/gal","base": 7.1,  "noise": 0.05},
        {"tag": "WATER_CUT",   "label": "Water Cut",             "unit": "%",     "base": 0.8,  "noise": 0.1},
    ],
    "PIG_LAUNCHER": [
        {"tag": "PRESS",       "label": "Barrel Pressure",       "unit": "psig",  "base": 0,    "noise": 0},
        {"tag": "DOOR_STATUS", "label": "Door Status",           "unit": "",      "base": 1,    "noise": 0},
    ],
    "PIG_RECEIVER": [
        {"tag": "PRESS",       "label": "Barrel Pressure",       "unit": "psig",  "base": 0,    "noise": 0},
        {"tag": "DOOR_STATUS", "label": "Door Status",           "unit": "",      "base": 1,    "noise": 0},
    ],
    "VALVE_STATION": [
        {"tag": "PRESS_UP",    "label": "Upstream Pressure",     "unit": "psig",  "base": 1050, "noise": 12},
        {"tag": "PRESS_DN",    "label": "Downstream Pressure",   "unit": "psig",  "base": 1040, "noise": 12},
        {"tag": "POSITION",    "label": "Valve Position",        "unit": "%",     "base": 100,  "noise": 0},
        {"tag": "ACTUATOR_P",  "label": "Actuator Pressure",     "unit": "psig",  "base": 80,   "noise": 2},
    ],
    "RTU": [
        {"tag": "CPU_LOAD",    "label": "CPU Load",              "unit": "%",     "base": 28,   "noise": 5},
        {"tag": "SIGNAL_STR",  "label": "Signal Strength",       "unit": "dBm",   "base": -55,  "noise": 3},
        {"tag": "BATT_V",      "label": "Battery Voltage",       "unit": "V",     "base": 12.6, "noise": 0.1},
        {"tag": "COMM_OK",     "label": "Comms Status",          "unit": "",      "base": 1,    "noise": 0},
    ],
    "CP_SYSTEM": [
        {"tag": "RECT_V",      "label": "Rectifier Voltage",     "unit": "V",     "base": 24,   "noise": 0.5},
        {"tag": "RECT_A",      "label": "Rectifier Current",     "unit": "A",     "base": 8.5,  "noise": 0.3},
        {"tag": "PIPE_POT",    "label": "Pipe-to-Soil Potential","unit": "mV",    "base": -920, "noise": 15},
    ],
}

# ── RUL Predictions ────────────────────────────────────────────────
RUL_PREDICTIONS = [
    {"asset_id": "SEG-01",  "predicted_rul_days": 680,  "failure_prob_7d": 0.01, "failure_prob_30d": 0.03, "model_version": "rul_xgb_pipe_v2.4"},
    {"asset_id": "SEG-02",  "predicted_rul_days": 420,  "failure_prob_7d": 0.02, "failure_prob_30d": 0.06, "model_version": "rul_xgb_pipe_v2.4"},
    {"asset_id": "SEG-03",  "predicted_rul_days": 310,  "failure_prob_7d": 0.03, "failure_prob_30d": 0.09, "model_version": "rul_xgb_pipe_v2.4"},
    {"asset_id": "CS-01",   "predicted_rul_days": 195,  "failure_prob_7d": 0.04, "failure_prob_30d": 0.12, "model_version": "rul_lstm_comp_v1.8"},
    {"asset_id": "CS-02",   "predicted_rul_days": 240,  "failure_prob_7d": 0.03, "failure_prob_30d": 0.10, "model_version": "rul_lstm_comp_v1.8"},
    {"asset_id": "PS-01",   "predicted_rul_days": 155,  "failure_prob_7d": 0.05, "failure_prob_30d": 0.14, "model_version": "rul_xgb_pump_v3.1"},
    {"asset_id": "PS-02",   "predicted_rul_days": 210,  "failure_prob_7d": 0.03, "failure_prob_30d": 0.08, "model_version": "rul_xgb_pump_v3.1"},
    {"asset_id": "VLV-01",  "predicted_rul_days": 520,  "failure_prob_7d": 0.01, "failure_prob_30d": 0.02, "model_version": "rul_rf_valve_v2.0"},
    {"asset_id": "VLV-02",  "predicted_rul_days": 380,  "failure_prob_7d": 0.02, "failure_prob_30d": 0.05, "model_version": "rul_rf_valve_v2.0"},
    {"asset_id": "CP-01",   "predicted_rul_days": 730,  "failure_prob_7d": 0.01, "failure_prob_30d": 0.02, "model_version": "rul_lr_cp_v1.2"},
]

# ── Failure Patterns ───────────────────────────────────────────────
FAILURE_PATTERNS = [
    {
        "component_type": "PIPE_SEGMENT", "failure_mode": "EXTERNAL_CORROSION",
        "root_cause": "Coating disbondment with inadequate cathodic protection",
        "avg_ttf_days": 180, "action": "Excavate, assess wall thickness, apply composite repair sleeve",
        "downtime_hours": 48,
    },
    {
        "component_type": "PIPE_SEGMENT", "failure_mode": "PRESSURE_EXCURSION",
        "root_cause": "Surge from rapid valve closure or compressor trip",
        "avg_ttf_days": 0, "action": "Reduce throughput, check relief valves, investigate surge source",
        "downtime_hours": 4,
    },
    {
        "component_type": "COMPRESSOR", "failure_mode": "HIGH_VIBRATION",
        "root_cause": "Impeller imbalance or bearing degradation",
        "avg_ttf_days": 28, "action": "Schedule bearing replacement, reduce load, monitor trend",
        "downtime_hours": 16,
    },
    {
        "component_type": "COMPRESSOR", "failure_mode": "SURGE",
        "root_cause": "Operating below minimum stable flow — anti-surge valve malfunction",
        "avg_ttf_days": 0, "action": "Open recycle valve, verify anti-surge controller, reduce discharge pressure",
        "downtime_hours": 2,
    },
    {
        "component_type": "PUMP_STATION", "failure_mode": "SEAL_LEAK",
        "root_cause": "Mechanical seal wear from high-solids crude or misalignment",
        "avg_ttf_days": 35, "action": "Switch to standby pump, replace mechanical seal, flush seal system",
        "downtime_hours": 12,
    },
    {
        "component_type": "VALVE_STATION", "failure_mode": "SLOW_STROKE",
        "root_cause": "Actuator hydraulic leak or corroded stem",
        "avg_ttf_days": 60, "action": "Partial-stroke test, inspect actuator, replace hydraulic seals",
        "downtime_hours": 8,
    },
    {
        "component_type": "METERING", "failure_mode": "DRIFT",
        "root_cause": "Turbine blade erosion or prover calibration shift",
        "avg_ttf_days": 90, "action": "Recalibrate against master meter, inspect internals",
        "downtime_hours": 6,
    },
    {
        "component_type": "CP_SYSTEM", "failure_mode": "UNDER_PROTECTION",
        "root_cause": "Rectifier output degradation or anode bed depletion",
        "avg_ttf_days": 120, "action": "Increase rectifier output, survey anode bed, consider anode replacement",
        "downtime_hours": 4,
    },
]

# ── SAP / CMMS Work Orders ─────────────────────────────────────────
WORK_ORDERS = [
    {"wo_id": "WO-600101", "asset_id": "CS-01",  "title": "Compressor Alpha — bearing inspection",      "status": "OPEN",        "priority": "P1"},
    {"wo_id": "WO-600102", "asset_id": "PS-01",  "title": "Pump Station 1 — mechanical seal replacement","status": "IN_PROGRESS", "priority": "P1"},
    {"wo_id": "WO-600103", "asset_id": "SEG-02", "title": "Segment 2 — ILI anomaly dig verification",    "status": "PLANNED",     "priority": "P2"},
    {"wo_id": "WO-600104", "asset_id": "VLV-02", "title": "Block Valve 2 — partial-stroke test",         "status": "OPEN",        "priority": "P2"},
    {"wo_id": "WO-600105", "asset_id": "MET-02", "title": "Delivery meter — prover calibration",         "status": "PLANNED",     "priority": "P3"},
    {"wo_id": "WO-600106", "asset_id": "CP-01",  "title": "CP rectifier bank — output survey",           "status": "COMPLETED",   "priority": "P3"},
    {"wo_id": "WO-600107", "asset_id": "SEG-01", "title": "Gathering line — coating condition survey",   "status": "PLANNED",     "priority": "P2"},
]

# ── Spare Parts Inventory ──────────────────────────────────────────
SPARE_PARTS = [
    {"part_id": "MAT-7001", "description": "24″ Composite Repair Sleeve",      "qty": 3,  "min_qty": 2, "lead_days": 21, "unit_cost": 28000},
    {"part_id": "MAT-7002", "description": "Compressor Bearing Kit (radial)",   "qty": 4,  "min_qty": 2, "lead_days": 14, "unit_cost": 18500},
    {"part_id": "MAT-7003", "description": "Mechanical Seal Assembly — 8″",     "qty": 2,  "min_qty": 2, "lead_days": 10, "unit_cost": 9200},
    {"part_id": "MAT-7004", "description": "Block Valve Actuator Seal Kit",     "qty": 6,  "min_qty": 3, "lead_days": 7,  "unit_cost": 3400},
    {"part_id": "MAT-7005", "description": "Turbine Meter Rotor Assembly",      "qty": 1,  "min_qty": 1, "lead_days": 28, "unit_cost": 42000},
    {"part_id": "MAT-7006", "description": "SCADA RTU Communication Module",    "qty": 3,  "min_qty": 2, "lead_days": 14, "unit_cost": 5600},
    {"part_id": "MAT-7007", "description": "CP Anode — High-Silicon Cast Iron", "qty": 12, "min_qty": 6, "lead_days": 30, "unit_cost": 1800},
    {"part_id": "MAT-7008", "description": "Pig — MFL Inspection Tool 24″",    "qty": 1,  "min_qty": 1, "lead_days": 45, "unit_cost": 125000},
    {"part_id": "MAT-7009", "description": "Anti-Surge Valve (6″ Fisher)",      "qty": 1,  "min_qty": 1, "lead_days": 35, "unit_cost": 67000},
    {"part_id": "MAT-7010", "description": "Motor Starter Contactor 480V",      "qty": 2,  "min_qty": 1, "lead_days": 7,  "unit_cost": 2100},
]

# ── Crew Roster ────────────────────────────────────────────────────
CREW = [
    {"name": "Marcus Reeves",   "role": "Pipeline Engineer",        "shift": "Day",   "zone": "CONTROL_CENTER",   "certs": ["API_1169", "NACE_CP2", "PIPELINE_INTEGRITY"]},
    {"name": "Angela Torres",   "role": "Compressor Technician",    "shift": "Day",   "zone": "CS_ALPHA",         "certs": ["COMPRESSOR_MAINT", "GAS_DETECTION", "CONFINED_SPACE"]},
    {"name": "Brian Kowalski",  "role": "Pump Station Operator",    "shift": "Day",   "zone": "PS_MAINLINE",      "certs": ["PUMP_OPERATIONS", "ELECTRICAL_HV", "FIRST_AID"]},
    {"name": "Priya Sharma",    "role": "SCADA Engineer",           "shift": "Day",   "zone": "CONTROL_CENTER",   "certs": ["SCADA_ADMIN", "CYBERSECURITY_ICS", "PLC_CERTIFIED"]},
    {"name": "Tom Henriksen",   "role": "Corrosion Engineer",       "shift": "Day",   "zone": "FIELD_OFFICE",     "certs": ["NACE_CP3", "NACE_CIP2", "PIPELINE_INTEGRITY"]},
    {"name": "Diana Okafor",    "role": "Pipeline Technician",      "shift": "Night", "zone": "QUARTERS",         "certs": ["API_1169", "PIPELINE_MAINT", "HOT_TAP_CERTIFIED"]},
    {"name": "James Whitfield", "role": "Operations Superintendent","shift": "Day",   "zone": "ADMIN_OFFICE",     "certs": ["OQ_QUALIFIED", "API_1160", "EMERGENCY_RESPONSE"]},
    {"name": "Rachel Kim",      "role": "HSE Specialist",           "shift": "Day",   "zone": "HSE_OFFICE",       "certs": ["NEBOSH", "OSHA_30", "HAZWOPER", "FIRST_AID"]},
]

# ── Certification → Asset Type Mapping ─────────────────────────────
CERT_TO_ASSET: dict[str, list[str]] = {
    "API_1169":           ["PIPE_SEGMENT", "VALVE_STATION", "PIG_LAUNCHER", "PIG_RECEIVER"],
    "PIPELINE_INTEGRITY": ["PIPE_SEGMENT", "CP_SYSTEM"],
    "PIPELINE_MAINT":     ["PIPE_SEGMENT", "VALVE_STATION", "PIG_LAUNCHER", "PIG_RECEIVER"],
    "COMPRESSOR_MAINT":   ["COMPRESSOR"],
    "PUMP_OPERATIONS":    ["PUMP_STATION"],
    "ELECTRICAL_HV":      ["PUMP_STATION", "COMPRESSOR", "CP_SYSTEM"],
    "SCADA_ADMIN":        ["RTU"],
    "PLC_CERTIFIED":      ["RTU"],
    "NACE_CP2":           ["CP_SYSTEM", "PIPE_SEGMENT"],
    "NACE_CP3":           ["CP_SYSTEM", "PIPE_SEGMENT"],
    "NACE_CIP2":          ["PIPE_SEGMENT"],
    "HOT_TAP_CERTIFIED":  ["PIPE_SEGMENT"],
    "OQ_QUALIFIED":       ["PIPE_SEGMENT", "VALVE_STATION", "PUMP_STATION", "COMPRESSOR"],
}

# ── Skill Tier (primary expertise vs general qualification) ───────
# Higher tier = more specialized match for the asset type
CERT_TIER: dict[str, int] = {
    "API_1169": 3, "PIPELINE_INTEGRITY": 3, "NACE_CP3": 3,
    "COMPRESSOR_MAINT": 3, "PUMP_OPERATIONS": 3, "SCADA_ADMIN": 3,
    "NACE_CP2": 2, "NACE_CIP2": 2, "PIPELINE_MAINT": 2,
    "ELECTRICAL_HV": 2, "PLC_CERTIFIED": 2, "HOT_TAP_CERTIFIED": 2,
    "OQ_QUALIFIED": 1, "GAS_DETECTION": 1, "CONFINED_SPACE": 1,
    "FIRST_AID": 1, "HAZWOPER": 1, "OSHA_30": 1, "NEBOSH": 1,
    "CYBERSECURITY_ICS": 1, "EMERGENCY_RESPONSE": 1,
}

# ── Incident Complexity → Required Crew Roles ────────────────────
# Maps (asset_type, severity) → list of required skill categories
INCIDENT_CREW_MATRIX: dict[tuple[str, int], list[dict]] = {
    # CRITICAL incidents need specialist + safety
    ("PIPE_SEGMENT", 3):  [
        {"role": "Lead", "certs": ["API_1169", "PIPELINE_INTEGRITY", "NACE_CIP2"], "required": True},
        {"role": "Corrosion Specialist", "certs": ["NACE_CP3", "NACE_CP2", "NACE_CIP2"], "required": True},
        {"role": "HSE Standby", "certs": ["HAZWOPER", "OSHA_30", "NEBOSH", "EMERGENCY_RESPONSE"], "required": False},
    ],
    ("PIPE_SEGMENT", 2):  [
        {"role": "Lead", "certs": ["API_1169", "PIPELINE_MAINT", "PIPELINE_INTEGRITY"], "required": True},
    ],
    ("COMPRESSOR", 3):    [
        {"role": "Lead Mechanic", "certs": ["COMPRESSOR_MAINT"], "required": True},
        {"role": "Electrical Support", "certs": ["ELECTRICAL_HV"], "required": True},
        {"role": "HSE Standby", "certs": ["HAZWOPER", "OSHA_30", "NEBOSH", "EMERGENCY_RESPONSE"], "required": False},
    ],
    ("COMPRESSOR", 2):    [
        {"role": "Mechanic", "certs": ["COMPRESSOR_MAINT"], "required": True},
    ],
    ("PUMP_STATION", 3):  [
        {"role": "Pump Operator", "certs": ["PUMP_OPERATIONS"], "required": True},
        {"role": "Electrical Support", "certs": ["ELECTRICAL_HV"], "required": True},
        {"role": "HSE Standby", "certs": ["HAZWOPER", "OSHA_30", "NEBOSH", "EMERGENCY_RESPONSE"], "required": False},
    ],
    ("PUMP_STATION", 2):  [
        {"role": "Pump Operator", "certs": ["PUMP_OPERATIONS"], "required": True},
    ],
    ("METERING", 3):      [
        {"role": "I&E Technician", "certs": ["PIPELINE_MAINT", "OQ_QUALIFIED"], "required": True},
    ],
    ("METERING", 2):      [
        {"role": "I&E Technician", "certs": ["PIPELINE_MAINT", "OQ_QUALIFIED"], "required": True},
    ],
    ("VALVE_STATION", 3): [
        {"role": "Lead", "certs": ["API_1169", "PIPELINE_MAINT"], "required": True},
        {"role": "Ops Supervisor", "certs": ["OQ_QUALIFIED", "API_1160", "EMERGENCY_RESPONSE"], "required": True},
    ],
    ("VALVE_STATION", 2): [
        {"role": "Technician", "certs": ["API_1169", "PIPELINE_MAINT"], "required": True},
    ],
    ("RTU", 3):           [
        {"role": "SCADA Engineer", "certs": ["SCADA_ADMIN", "PLC_CERTIFIED", "CYBERSECURITY_ICS"], "required": True},
    ],
    ("RTU", 2):           [
        {"role": "SCADA Technician", "certs": ["SCADA_ADMIN", "PLC_CERTIFIED"], "required": True},
    ],
    ("CP_SYSTEM", 3):     [
        {"role": "CP Specialist", "certs": ["NACE_CP3", "NACE_CP2"], "required": True},
        {"role": "Pipeline Support", "certs": ["PIPELINE_INTEGRITY", "API_1169"], "required": False},
    ],
    ("CP_SYSTEM", 2):     [
        {"role": "CP Technician", "certs": ["NACE_CP3", "NACE_CP2", "PIPELINE_INTEGRITY"], "required": True},
    ],
}

# Maximum concurrent assignments per crew member before flagging overload
MAX_CONCURRENT_ASSIGNMENTS = 2

# ── Zone-Based Intervention ETAs (minutes) ─────────────────────────
ZONE_ETA: dict[str, int] = {
    "CONTROL_CENTER": 2,
    "CS_ALPHA":       5,
    "PS_MAINLINE":    8,
    "FIELD_OFFICE":   10,
    "ADMIN_OFFICE":   6,
    "HSE_OFFICE":     7,
    "QUARTERS":       20,
}
NIGHT_SHIFT_PENALTY = 25  # extra minutes for night-shift callout

# ── Pipeline Operations Cycle (rotating every 8 ticks) ─────────────
OPERATIONS_CYCLE = [
    {"op": "STEADY_STATE",   "detail": "Normal throughput 8 500 bbl/h",                 "risk": "LOW"},
    {"op": "RATE_CHANGE",    "detail": "Ramp-up to 9 200 bbl/h per shipper nomination", "risk": "LOW"},
    {"op": "PIG_RUN",        "detail": "MFL inspection pig — launched from PIG-01",     "risk": "MEDIUM"},
    {"op": "SHUTDOWN_MAINT", "detail": "CS-01 planned maintenance window",              "risk": "MEDIUM"},
    {"op": "RESTART",        "detail": "Pipeline pack and restart after maintenance",   "risk": "HIGH"},
]

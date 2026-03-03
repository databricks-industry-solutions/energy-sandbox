"""
Simulated SAP PM data for all 12 ESP wells.
Uses realistic SAP field values (EQUI, QMEL, AUFK tables).
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Base date for relative date generation
_BASE = datetime(2026, 2, 22)


def _dt(delta_days: int) -> str:
    return (_BASE + timedelta(days=delta_days)).strftime("%Y-%m-%d")


# SAP Equipment Master data (EQUI table)
_EQUIPMENT: Dict[str, Dict[str, Any]] = {
    "ESP-001": {"EQUNR": "10001234", "EQKTX": "Electric Submersible Pump - Meridian-1A",     "INGRP": "I01", "HERST": "Baker Hughes REDA",    "SERGE": "BH-REDA-D950N-001", "BAUJJ": "2023", "ANLNR": "100023401"},
    "ESP-002": {"EQUNR": "10001235", "EQKTX": "Electric Submersible Pump - Meridian-2B",     "INGRP": "I01", "HERST": "Baker Hughes REDA",    "SERGE": "BH-REDA-D950N-002", "BAUJJ": "2023", "ANLNR": "100023402"},
    "ESP-003": {"EQUNR": "10001236", "EQKTX": "Electric Submersible Pump - Crawford-1",      "INGRP": "I02", "HERST": "Schlumberger",          "SERGE": "SLB-GN4000-003",    "BAUJJ": "2022", "ANLNR": "100023403"},
    "ESP-004": {"EQUNR": "10001237", "EQKTX": "Electric Submersible Pump - Crawford-3A",     "INGRP": "I02", "HERST": "Schlumberger",          "SERGE": "SLB-GN4000-004",    "BAUJJ": "2025", "ANLNR": "100023404"},
    "ESP-005": {"EQUNR": "10001238", "EQKTX": "Electric Submersible Pump - Oakhurst-7",      "INGRP": "I03", "HERST": "Borets",                "SERGE": "BOR-D600-005",      "BAUJJ": "2022", "ANLNR": "100023405"},
    "ESP-006": {"EQUNR": "10001239", "EQKTX": "Electric Submersible Pump - Oakhurst-12",     "INGRP": "I03", "HERST": "Borets",                "SERGE": "BOR-D600-006",      "BAUJJ": "2024", "ANLNR": "100023406"},
    "ESP-007": {"EQUNR": "10001240", "EQKTX": "Electric Submersible Pump - Redstone-4",      "INGRP": "I04", "HERST": "Baker Hughes REDA",    "SERGE": "BH-REDA-DN1750-007","BAUJJ": "2023", "ANLNR": "100023407"},
    "ESP-008": {"EQUNR": "10001241", "EQKTX": "Electric Submersible Pump - Redstone-9A",     "INGRP": "I04", "HERST": "Baker Hughes REDA",    "SERGE": "BH-REDA-DN1750-008","BAUJJ": "2023", "ANLNR": "100023408"},
    "ESP-009": {"EQUNR": "10001242", "EQKTX": "Electric Submersible Pump - Sunrise-2",       "INGRP": "I05", "HERST": "Schlumberger",          "SERGE": "SLB-FLEX31-009",    "BAUJJ": "2021", "ANLNR": "100023409"},
    "ESP-010": {"EQUNR": "10001243", "EQKTX": "Electric Submersible Pump - Sunrise-5B",      "INGRP": "I05", "HERST": "Schlumberger",          "SERGE": "SLB-FLEX31-010",    "BAUJJ": "2024", "ANLNR": "100023410"},
    "ESP-011": {"EQUNR": "10001244", "EQKTX": "Electric Submersible Pump - Prairie-1",       "INGRP": "I01", "HERST": "Centrilift (Baker Hughes)","SERGE":"CL-GN3600-011",    "BAUJJ": "2025", "ANLNR": "100023411"},
    "ESP-012": {"EQUNR": "10001245", "EQKTX": "Electric Submersible Pump - Prairie-3",       "INGRP": "I01", "HERST": "Centrilift (Baker Hughes)","SERGE":"CL-GN3600-012",    "BAUJJ": "2025", "ANLNR": "100023412"},
}

# Open Notifications (QMEL) — only wells with active issues
_NOTIFICATIONS: Dict[str, List[Dict[str, Any]]] = {
    "ESP-002": [
        {"QMNUM": "1000087321", "QMTXT": "Gas interference causing PIP drop below threshold",          "QMART": "M1", "PRIOK": "2", "MNCOD": "GAS", "ERDAT": _dt(-3)},
        {"QMNUM": "1000087322", "QMTXT": "Scheduled lubrication and vibration check Q1",               "QMART": "M3", "PRIOK": "4", "MNCOD": "LUB", "ERDAT": _dt(-14)},
    ],
    "ESP-003": [
        {"QMNUM": "1000087330", "QMTXT": "High vibration signal on radial bearing - inspect within 72h","QMART": "M1","PRIOK": "1", "MNCOD": "VIB", "ERDAT": _dt(-1)},
        {"QMNUM": "1000087331", "QMTXT": "Elevated motor winding temperature trend",                    "QMART": "M1","PRIOK": "2", "MNCOD": "TMP", "ERDAT": _dt(-2)},
    ],
    "ESP-005": [
        {"QMNUM": "1000087345", "QMTXT": "Pump stage wear - efficiency below 55%",                     "QMART": "M1", "PRIOK": "2", "MNCOD": "EFF", "ERDAT": _dt(-5)},
    ],
    "ESP-007": [
        {"QMNUM": "1000087360", "QMTXT": "Motor overload - current at 115% nameplate",                 "QMART": "M1", "PRIOK": "1", "MNCOD": "CUR", "ERDAT": _dt(-1)},
        {"QMNUM": "1000087361", "QMTXT": "Review VSD frequency set point - possible over-speed",       "QMART": "M2", "PRIOK": "2", "MNCOD": "FRQ", "ERDAT": _dt(-2)},
    ],
    "ESP-009": [
        {"QMNUM": "1000087375", "QMTXT": "CRITICAL: Motor winding temp exceeds 205°F - shutdown risk", "QMART": "M1", "PRIOK": "1", "MNCOD": "TMP", "ERDAT": _dt(0)},
        {"QMNUM": "1000087376", "QMTXT": "Elevated fluid temperature - check produced water ratio",    "QMART": "M2", "PRIOK": "2", "MNCOD": "TMP", "ERDAT": _dt(-1)},
    ],
    "ESP-010": [
        {"QMNUM": "1000087390", "QMTXT": "Scale buildup - discharge pressure rising trend",            "QMART": "M1", "PRIOK": "2", "MNCOD": "SCL", "ERDAT": _dt(-6)},
        {"QMNUM": "1000087391", "QMTXT": "Request chemical treatment - scale inhibitor injection",     "QMART": "M2", "PRIOK": "3", "MNCOD": "CHM", "ERDAT": _dt(-4)},
    ],
}

# Work Orders (AUFK) — open orders
_WORK_ORDERS: Dict[str, List[Dict[str, Any]]] = {
    "ESP-002": [
        {"AUFNR": "4000123401", "KTEXT": "Inspect pump intake for gas slugging - optimize drawdown",  "AUART": "PM02", "FTRMS": _dt(5),  "STATU": "REL", "GWLDT": _dt(7),  "PRIOK": "2", "TECH": "J.Martinez"},
    ],
    "ESP-003": [
        {"AUFNR": "4000123410", "KTEXT": "Replace radial bearing assembly - bearing wear confirmed",   "AUART": "PM02", "FTRMS": _dt(1),  "STATU": "REL", "GWLDT": _dt(3),  "PRIOK": "1", "TECH": "R.Thompson"},
        {"AUFNR": "4000123411", "KTEXT": "Motor temperature investigation and cable check",            "AUART": "PM03", "FTRMS": _dt(2),  "STATU": "CRTD","GWLDT": _dt(4),  "PRIOK": "2", "TECH": "A.Singh"},
    ],
    "ESP-005": [
        {"AUFNR": "4000123425", "KTEXT": "Workover evaluation - pump stage replacement decision",      "AUART": "PM02", "FTRMS": _dt(10), "STATU": "REL", "GWLDT": _dt(14), "PRIOK": "2", "TECH": "K.Williams"},
    ],
    "ESP-007": [
        {"AUFNR": "4000123440", "KTEXT": "Reduce VSD frequency to 48 Hz - motor overload mitigation", "AUART": "PM02", "FTRMS": _dt(0),  "STATU": "REL", "GWLDT": _dt(1),  "PRIOK": "1", "TECH": "D.Patel"},
    ],
    "ESP-009": [
        {"AUFNR": "4000123455", "KTEXT": "URGENT: Shutdown ESP-009 - critical temperature exceeded",  "AUART": "PM02", "FTRMS": _dt(0),  "STATU": "REL", "GWLDT": _dt(0),  "PRIOK": "1", "TECH": "R.Thompson"},
    ],
    "ESP-010": [
        {"AUFNR": "4000123470", "KTEXT": "Chemical scale treatment - inject EDTA scale inhibitor",    "AUART": "PM02", "FTRMS": _dt(3),  "STATU": "CRTD","GWLDT": _dt(5),  "PRIOK": "2", "TECH": "M.Garcia"},
        {"AUFNR": "4000123471", "KTEXT": "Q1 Planned maintenance - scale inspection and cleaning",    "AUART": "PM01", "FTRMS": _dt(30), "STATU": "CRTD","GWLDT": _dt(35), "PRIOK": "3", "TECH": "J.Martinez"},
    ],
}

# PM Schedule — next planned maintenance date per well
_PM_SCHEDULE: Dict[str, str] = {
    "ESP-001": _dt(45),
    "ESP-002": _dt(5),
    "ESP-003": _dt(1),
    "ESP-004": _dt(60),
    "ESP-005": _dt(10),
    "ESP-006": _dt(55),
    "ESP-007": _dt(0),
    "ESP-008": _dt(40),
    "ESP-009": _dt(0),
    "ESP-010": _dt(3),
    "ESP-011": _dt(90),
    "ESP-012": _dt(75),
}

# Maintenance history — last 5 completed orders per well
_HISTORY: Dict[str, List[Dict[str, Any]]] = {
    "ESP-001": [
        {"AUFNR": "4000100001", "KTEXT": "Annual PM inspection - all parameters normal",            "AUART": "PM01", "IDAT": _dt(-90),  "TECH": "J.Martinez", "COST_USD": 4200},
        {"AUFNR": "4000099801", "KTEXT": "Cable integrity test and insulation check",               "AUART": "PM03", "IDAT": _dt(-180), "TECH": "A.Singh",    "COST_USD": 1800},
        {"AUFNR": "4000099601", "KTEXT": "VSD firmware upgrade and calibration",                   "AUART": "PM03", "IDAT": _dt(-270), "TECH": "D.Patel",    "COST_USD": 900},
        {"AUFNR": "4000099401", "KTEXT": "Pump downhole survey - baseline readings",               "AUART": "PM03", "IDAT": _dt(-360), "TECH": "R.Thompson", "COST_USD": 2100},
        {"AUFNR": "4000099201", "KTEXT": "Initial ESP installation and commissioning",             "AUART": "PM01", "IDAT": _dt(-450), "TECH": "M.Garcia",   "COST_USD": 45000},
    ],
    "ESP-002": [
        {"AUFNR": "4000100002", "KTEXT": "Gas interference mitigation - drawdown adjustment",      "AUART": "PM02", "IDAT": _dt(-45),  "TECH": "J.Martinez", "COST_USD": 3500},
        {"AUFNR": "4000099802", "KTEXT": "PIP sensor calibration and verification",                "AUART": "PM03", "IDAT": _dt(-120), "TECH": "A.Singh",    "COST_USD": 800},
        {"AUFNR": "4000099602", "KTEXT": "Annual PM - minor bearing wear noted",                   "AUART": "PM01", "IDAT": _dt(-210), "TECH": "D.Patel",    "COST_USD": 5200},
        {"AUFNR": "4000099402", "KTEXT": "Vibration analysis - all within limits",                 "AUART": "PM03", "IDAT": _dt(-300), "TECH": "R.Thompson", "COST_USD": 1200},
        {"AUFNR": "4000099202", "KTEXT": "Stage replacement - pump wear found",                    "AUART": "PM02", "IDAT": _dt(-420), "TECH": "K.Williams", "COST_USD": 28000},
    ],
    "ESP-003": [
        {"AUFNR": "4000100003", "KTEXT": "Emergency bearing inspection - vibration event",         "AUART": "PM02", "IDAT": _dt(-14),  "TECH": "R.Thompson", "COST_USD": 8500},
        {"AUFNR": "4000099803", "KTEXT": "Semi-annual PM - bearing wear noted at 2.1 mm/s",       "AUART": "PM01", "IDAT": _dt(-90),  "TECH": "A.Singh",    "COST_USD": 6800},
        {"AUFNR": "4000099603", "KTEXT": "Motor winding resistance test - within spec",            "AUART": "PM03", "IDAT": _dt(-180), "TECH": "D.Patel",    "COST_USD": 1400},
        {"AUFNR": "4000099403", "KTEXT": "Complete ESP overhaul - replaced seal section",          "AUART": "PM02", "IDAT": _dt(-365), "TECH": "K.Williams", "COST_USD": 62000},
        {"AUFNR": "4000099203", "KTEXT": "Annual PM - all parameters within limits",               "AUART": "PM01", "IDAT": _dt(-455), "TECH": "M.Garcia",   "COST_USD": 4800},
    ],
    "ESP-004": [
        {"AUFNR": "4000100004", "KTEXT": "Initial commissioning and baseline survey",              "AUART": "PM01", "IDAT": _dt(-30),  "TECH": "J.Martinez", "COST_USD": 52000},
        {"AUFNR": "4000099804", "KTEXT": "30-day performance evaluation",                          "AUART": "PM03", "IDAT": _dt(-33),  "TECH": "A.Singh",    "COST_USD": 1200},
        {"AUFNR": "4000099604", "KTEXT": "VSD tuning for optimal flow rate",                       "AUART": "PM03", "IDAT": _dt(-35),  "TECH": "D.Patel",    "COST_USD": 650},
        {"AUFNR": "4000099404", "KTEXT": "Cable continuity test pre-installation",                 "AUART": "PM03", "IDAT": _dt(-40),  "TECH": "R.Thompson", "COST_USD": 900},
        {"AUFNR": "4000099204", "KTEXT": "Pre-installation equipment inspection",                  "AUART": "PM03", "IDAT": _dt(-45),  "TECH": "M.Garcia",   "COST_USD": 1500},
    ],
    "ESP-005": [
        {"AUFNR": "4000100005", "KTEXT": "Pump efficiency test - confirmed wear pattern",          "AUART": "PM03", "IDAT": _dt(-20),  "TECH": "K.Williams", "COST_USD": 2800},
        {"AUFNR": "4000099805", "KTEXT": "Annual PM - efficiency at 58%, monitoring",              "AUART": "PM01", "IDAT": _dt(-90),  "TECH": "J.Martinez", "COST_USD": 5100},
        {"AUFNR": "4000099605", "KTEXT": "Flow meter calibration and verification",                "AUART": "PM03", "IDAT": _dt(-180), "TECH": "A.Singh",    "COST_USD": 750},
        {"AUFNR": "4000099405", "KTEXT": "Stage inspection - mild wear noted on impellers",       "AUART": "PM02", "IDAT": _dt(-280), "TECH": "D.Patel",    "COST_USD": 12000},
        {"AUFNR": "4000099205", "KTEXT": "Annual PM - new installation running well",             "AUART": "PM01", "IDAT": _dt(-370), "TECH": "K.Williams", "COST_USD": 4200},
    ],
    "ESP-006": [
        {"AUFNR": "4000100006", "KTEXT": "Semi-annual PM - all parameters nominal",               "AUART": "PM01", "IDAT": _dt(-45),  "TECH": "M.Garcia",   "COST_USD": 4000},
        {"AUFNR": "4000099806", "KTEXT": "Pressure transducer replacement",                       "AUART": "PM02", "IDAT": _dt(-75),  "TECH": "J.Martinez", "COST_USD": 1200},
        {"AUFNR": "4000099606", "KTEXT": "Annual PM - pump running efficiently",                   "AUART": "PM01", "IDAT": _dt(-135), "TECH": "R.Thompson", "COST_USD": 3800},
        {"AUFNR": "4000099406", "KTEXT": "Cable insulation inspection - passed",                  "AUART": "PM03", "IDAT": _dt(-225), "TECH": "A.Singh",    "COST_USD": 950},
        {"AUFNR": "4000099206", "KTEXT": "Initial ESP installation and commissioning",             "AUART": "PM01", "IDAT": _dt(-320), "TECH": "D.Patel",    "COST_USD": 48000},
    ],
    "ESP-007": [
        {"AUFNR": "4000100007", "KTEXT": "VSD over-current trip investigation",                    "AUART": "PM02", "IDAT": _dt(-7),   "TECH": "D.Patel",    "COST_USD": 4500},
        {"AUFNR": "4000099807", "KTEXT": "Annual PM - current trending high, monitoring",          "AUART": "PM01", "IDAT": _dt(-60),  "TECH": "K.Williams", "COST_USD": 5800},
        {"AUFNR": "4000099607", "KTEXT": "Motor winding test - slight degradation noted",         "AUART": "PM03", "IDAT": _dt(-145), "TECH": "J.Martinez", "COST_USD": 1600},
        {"AUFNR": "4000099407", "KTEXT": "Seal section replacement - minor leakage",              "AUART": "PM02", "IDAT": _dt(-240), "TECH": "R.Thompson", "COST_USD": 18000},
        {"AUFNR": "4000099207", "KTEXT": "Annual PM - running within specs",                      "AUART": "PM01", "IDAT": _dt(-330), "TECH": "M.Garcia",   "COST_USD": 5200},
    ],
    "ESP-008": [
        {"AUFNR": "4000100008", "KTEXT": "Semi-annual PM - excellent operating condition",         "AUART": "PM01", "IDAT": _dt(-60),  "TECH": "A.Singh",    "COST_USD": 4600},
        {"AUFNR": "4000099808", "KTEXT": "Vibration sensor recalibration",                         "AUART": "PM03", "IDAT": _dt(-90),  "TECH": "D.Patel",    "COST_USD": 700},
        {"AUFNR": "4000099608", "KTEXT": "Annual PM - all readings nominal",                      "AUART": "PM01", "IDAT": _dt(-180), "TECH": "J.Martinez", "COST_USD": 4200},
        {"AUFNR": "4000099408", "KTEXT": "Fluid sample analysis - no scale or corrosion",         "AUART": "PM03", "IDAT": _dt(-270), "TECH": "K.Williams", "COST_USD": 850},
        {"AUFNR": "4000099208", "KTEXT": "Initial installation and commissioning",                 "AUART": "PM01", "IDAT": _dt(-400), "TECH": "R.Thompson", "COST_USD": 51000},
    ],
    "ESP-009": [
        {"AUFNR": "4000100009", "KTEXT": "Temperature investigation - thermocouple replaced",      "AUART": "PM02", "IDAT": _dt(-30),  "TECH": "R.Thompson", "COST_USD": 3200},
        {"AUFNR": "4000099809", "KTEXT": "Annual PM - temp trending up, recommend monitoring",    "AUART": "PM01", "IDAT": _dt(-90),  "TECH": "M.Garcia",   "COST_USD": 6200},
        {"AUFNR": "4000099609", "KTEXT": "Coolant flow check and heat exchanger inspection",      "AUART": "PM03", "IDAT": _dt(-180), "TECH": "A.Singh",    "COST_USD": 2400},
        {"AUFNR": "4000099409", "KTEXT": "Motor rewind - winding insulation failure",             "AUART": "PM02", "IDAT": _dt(-420), "TECH": "K.Williams", "COST_USD": 85000},
        {"AUFNR": "4000099209", "KTEXT": "Annual PM - following motor rewind, all OK",            "AUART": "PM01", "IDAT": _dt(-510), "TECH": "D.Patel",    "COST_USD": 5800},
    ],
    "ESP-010": [
        {"AUFNR": "4000100010", "KTEXT": "Scale sampling and chemical treatment",                  "AUART": "PM02", "IDAT": _dt(-25),  "TECH": "J.Martinez", "COST_USD": 7500},
        {"AUFNR": "4000099810", "KTEXT": "Annual PM - early scale formation on stages",           "AUART": "PM01", "IDAT": _dt(-80),  "TECH": "R.Thompson", "COST_USD": 5400},
        {"AUFNR": "4000099610", "KTEXT": "Chemical inhibitor program initiation",                  "AUART": "PM02", "IDAT": _dt(-120), "TECH": "M.Garcia",   "COST_USD": 4200},
        {"AUFNR": "4000099410", "KTEXT": "Discharge valve inspection and cleaning",               "AUART": "PM03", "IDAT": _dt(-200), "TECH": "A.Singh",    "COST_USD": 1800},
        {"AUFNR": "4000099210", "KTEXT": "Initial installation and commissioning",                 "AUART": "PM01", "IDAT": _dt(-310), "TECH": "D.Patel",    "COST_USD": 49000},
    ],
    "ESP-011": [
        {"AUFNR": "4000100011", "KTEXT": "7-day performance review - running excellently",         "AUART": "PM03", "IDAT": _dt(-27),  "TECH": "K.Williams", "COST_USD": 800},
        {"AUFNR": "4000099811", "KTEXT": "Initial commissioning and 72h stabilization run",       "AUART": "PM01", "IDAT": _dt(-34),  "TECH": "J.Martinez", "COST_USD": 55000},
        {"AUFNR": "4000099611", "KTEXT": "Pre-installation equipment factory acceptance test",     "AUART": "PM03", "IDAT": _dt(-50),  "TECH": "R.Thompson", "COST_USD": 2200},
        {"AUFNR": "4000099411", "KTEXT": "Cable and motor megger test",                            "AUART": "PM03", "IDAT": _dt(-52),  "TECH": "A.Singh",    "COST_USD": 900},
        {"AUFNR": "4000099211", "KTEXT": "Wellbore preparation and casing inspection",            "AUART": "PM03", "IDAT": _dt(-60),  "TECH": "M.Garcia",   "COST_USD": 12000},
    ],
    "ESP-012": [
        {"AUFNR": "4000100012", "KTEXT": "30-day performance survey - all parameters stable",     "AUART": "PM03", "IDAT": _dt(-68),  "TECH": "D.Patel",    "COST_USD": 1100},
        {"AUFNR": "4000099812", "KTEXT": "Initial commissioning - Prairie-3",                      "AUART": "PM01", "IDAT": _dt(-98),  "TECH": "K.Williams", "COST_USD": 50000},
        {"AUFNR": "4000099612", "KTEXT": "VSD configuration and PID tuning",                       "AUART": "PM03", "IDAT": _dt(-100), "TECH": "J.Martinez", "COST_USD": 750},
        {"AUFNR": "4000099412", "KTEXT": "Cable installation and continuity test",                 "AUART": "PM03", "IDAT": _dt(-105), "TECH": "R.Thompson", "COST_USD": 8500},
        {"AUFNR": "4000099212", "KTEXT": "Wellbore survey and completion prep",                    "AUART": "PM03", "IDAT": _dt(-115), "TECH": "A.Singh",    "COST_USD": 15000},
    ],
}

# Name lookup
_WELL_NAMES = {w["esp_id"]: w["name"] for w in [
    {"esp_id": "ESP-001", "name": "Meridian-1A"},  {"esp_id": "ESP-002", "name": "Meridian-2B"},
    {"esp_id": "ESP-003", "name": "Crawford-1"},   {"esp_id": "ESP-004", "name": "Crawford-3A"},
    {"esp_id": "ESP-005", "name": "Oakhurst-7"},   {"esp_id": "ESP-006", "name": "Oakhurst-12"},
    {"esp_id": "ESP-007", "name": "Redstone-4"},   {"esp_id": "ESP-008", "name": "Redstone-9A"},
    {"esp_id": "ESP-009", "name": "Sunrise-2"},    {"esp_id": "ESP-010", "name": "Sunrise-5B"},
    {"esp_id": "ESP-011", "name": "Prairie-1"},    {"esp_id": "ESP-012", "name": "Prairie-3"},
]}


def get_sap_data(esp_id: str) -> Dict[str, Any]:
    """Return all SAP data for a given ESP ID."""
    return {
        "equipment":     _EQUIPMENT.get(esp_id, {}),
        "notifications": _NOTIFICATIONS.get(esp_id, []),
        "work_orders":   _WORK_ORDERS.get(esp_id, []),
        "pm_next_date":  _PM_SCHEDULE.get(esp_id, "N/A"),
        "history":       _HISTORY.get(esp_id, []),
        "well_name":     _WELL_NAMES.get(esp_id, esp_id),
    }


def get_all_open_work_orders() -> List[Dict[str, Any]]:
    """Return all open work orders across the fleet with well name attached."""
    result = []
    for esp_id, orders in _WORK_ORDERS.items():
        for wo in orders:
            result.append({
                **wo,
                "esp_id":    esp_id,
                "well_name": _WELL_NAMES.get(esp_id, esp_id),
            })
    # Sort by priority then FTRMS
    result.sort(key=lambda x: (x.get("PRIOK", "9"), x.get("FTRMS", "9999")))
    return result


def get_all_pm_schedule() -> List[Dict[str, Any]]:
    """Return PM schedule for all wells."""
    return [
        {"esp_id": esp_id, "well_name": _WELL_NAMES.get(esp_id, esp_id), "next_pm_date": date}
        for esp_id, date in _PM_SCHEDULE.items()
    ]

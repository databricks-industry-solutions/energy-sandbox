"""
Simulated SAP ERP data for MSEEL drilling operations.
Provides realistic SAP PM work orders, equipment BOM, procurement,
vendor contracts, and notifications for wells MIP_3H and MIP_4H.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_BASE = datetime(2026, 2, 25)


def _dt(delta_days: int) -> str:
    """Return an ISO date string offset from the base date."""
    return (_BASE + timedelta(days=delta_days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 1. Work Orders  (SAP PM – AUFK table style)
# ---------------------------------------------------------------------------
_WORK_ORDERS: list[dict[str, Any]] = [
    # ---- MIP_3H  (lateral section, actively drilling) ----
    {
        "wo_id": "WO-4000201001",
        "wo_type": "PM02",
        "well_id": "MIP_3H",
        "description": "Bit change - replace 8.5\" PDC bit at 9,450 ft MD (worn cutters)",
        "status": "IN_PROGRESS",
        "priority": 1,
        "created_date": _dt(-2),
        "due_date": _dt(0),
        "assigned_to": "J. Martinez",
        "cost_estimate": 48000.00,
        "actual_cost": 46200.00,
        "sap_notification": "NOTIF-300101",
    },
    {
        "wo_id": "WO-4000201002",
        "wo_type": "PM01",
        "well_id": "MIP_3H",
        "description": "BHA inspection - pull and inspect bottom-hole assembly after run 4",
        "status": "OPEN",
        "priority": 2,
        "created_date": _dt(-1),
        "due_date": _dt(2),
        "assigned_to": "R. Thompson",
        "cost_estimate": 12500.00,
        "actual_cost": None,
        "sap_notification": "NOTIF-300102",
    },
    {
        "wo_id": "WO-4000201003",
        "wo_type": "PM03",
        "well_id": "MIP_3H",
        "description": "MWD calibration - azimuth drift >0.3 deg observed in survey",
        "status": "OPEN",
        "priority": 2,
        "created_date": _dt(-1),
        "due_date": _dt(1),
        "assigned_to": "A. Singh",
        "cost_estimate": 8200.00,
        "actual_cost": None,
        "sap_notification": "NOTIF-300103",
    },
    {
        "wo_id": "WO-4000201004",
        "wo_type": "PM02",
        "well_id": "MIP_3H",
        "description": "Mud motor stall - replace 6-3/4\" mud motor (exceeded 120 hrs)",
        "status": "COMPLETED",
        "priority": 1,
        "created_date": _dt(-6),
        "due_date": _dt(-4),
        "assigned_to": "D. Patel",
        "cost_estimate": 35000.00,
        "actual_cost": 33800.00,
        "sap_notification": "NOTIF-300104",
    },
    {
        "wo_id": "WO-4000201005",
        "wo_type": "PM01",
        "well_id": "MIP_3H",
        "description": "Scheduled mud system maintenance - shaker screen replacement",
        "status": "OPEN",
        "priority": 3,
        "created_date": _dt(-3),
        "due_date": _dt(3),
        "assigned_to": "K. Williams",
        "cost_estimate": 4800.00,
        "actual_cost": None,
        "sap_notification": "NOTIF-300105",
    },
    {
        "wo_id": "WO-4000201006",
        "wo_type": "PM02",
        "well_id": "MIP_3H",
        "description": "Pump liner replacement - #2 mud pump liner cracked",
        "status": "IN_PROGRESS",
        "priority": 1,
        "created_date": _dt(-1),
        "due_date": _dt(0),
        "assigned_to": "M. Garcia",
        "cost_estimate": 6500.00,
        "actual_cost": 6100.00,
        "sap_notification": "NOTIF-300106",
    },
    {
        "wo_id": "WO-4000201007",
        "wo_type": "PM03",
        "well_id": "MIP_3H",
        "description": "Standpipe pressure gauge calibration and manifold leak check",
        "status": "CLOSED",
        "priority": 4,
        "created_date": _dt(-10),
        "due_date": _dt(-7),
        "assigned_to": "J. Martinez",
        "cost_estimate": 1200.00,
        "actual_cost": 1150.00,
        "sap_notification": "NOTIF-300107",
    },
    # ---- MIP_4H  (curve section, drilling ahead) ----
    {
        "wo_id": "WO-4000201008",
        "wo_type": "PM02",
        "well_id": "MIP_4H",
        "description": "Bit change - replace 8.5\" PDC bit at 7,820 ft MD (ROP decline)",
        "status": "OPEN",
        "priority": 2,
        "created_date": _dt(0),
        "due_date": _dt(2),
        "assigned_to": "R. Thompson",
        "cost_estimate": 48000.00,
        "actual_cost": None,
        "sap_notification": "NOTIF-300108",
    },
    {
        "wo_id": "WO-4000201009",
        "wo_type": "PM01",
        "well_id": "MIP_4H",
        "description": "Scheduled LWD tool maintenance - gamma ray source check",
        "status": "OPEN",
        "priority": 3,
        "created_date": _dt(-2),
        "due_date": _dt(4),
        "assigned_to": "A. Singh",
        "cost_estimate": 9500.00,
        "actual_cost": None,
        "sap_notification": None,
    },
    {
        "wo_id": "WO-4000201010",
        "wo_type": "PM02",
        "well_id": "MIP_4H",
        "description": "Stabilizer blade wear - replace 8-1/2\" string stabilizer",
        "status": "IN_PROGRESS",
        "priority": 2,
        "created_date": _dt(-3),
        "due_date": _dt(0),
        "assigned_to": "D. Patel",
        "cost_estimate": 14000.00,
        "actual_cost": 13600.00,
        "sap_notification": "NOTIF-300109",
    },
    {
        "wo_id": "WO-4000201011",
        "wo_type": "PM03",
        "well_id": "MIP_4H",
        "description": "Top-drive service - inspect swivel bearings and torque wrench cal",
        "status": "COMPLETED",
        "priority": 3,
        "created_date": _dt(-8),
        "due_date": _dt(-5),
        "assigned_to": "K. Williams",
        "cost_estimate": 7200.00,
        "actual_cost": 6950.00,
        "sap_notification": None,
    },
    {
        "wo_id": "WO-4000201012",
        "wo_type": "PM01",
        "well_id": "MIP_4H",
        "description": "Mud weight increase - transition to 11.2 ppg for curve build",
        "status": "COMPLETED",
        "priority": 2,
        "created_date": _dt(-5),
        "due_date": _dt(-3),
        "assigned_to": "M. Garcia",
        "cost_estimate": 18000.00,
        "actual_cost": 17400.00,
        "sap_notification": "NOTIF-300110",
    },
    {
        "wo_id": "WO-4000201013",
        "wo_type": "PM02",
        "well_id": "MIP_4H",
        "description": "Casing running - run and cement 9-5/8\" surface casing to 2,150 ft",
        "status": "CLOSED",
        "priority": 1,
        "created_date": _dt(-18),
        "due_date": _dt(-14),
        "assigned_to": "R. Thompson",
        "cost_estimate": 125000.00,
        "actual_cost": 121500.00,
        "sap_notification": None,
    },
    {
        "wo_id": "WO-4000201014",
        "wo_type": "PM03",
        "well_id": "MIP_3H",
        "description": "Derrick/crown block inspection - monthly safety compliance",
        "status": "OPEN",
        "priority": 4,
        "created_date": _dt(-1),
        "due_date": _dt(5),
        "assigned_to": "J. Martinez",
        "cost_estimate": 2200.00,
        "actual_cost": None,
        "sap_notification": None,
    },
]

# ---------------------------------------------------------------------------
# 2. Equipment / BOM  (SAP Material Master – MARA / MARC tables)
# ---------------------------------------------------------------------------
_EQUIPMENT_BOM: list[dict[str, Any]] = [
    # Bits
    {
        "material_id": "MAT-PDC-850",
        "description": "PDC Bit 8-1/2\" (5-blade, 16mm cutters)",
        "material_group": "BITS",
        "unit": "EA",
        "stock_qty": 4,
        "min_stock": 3,
        "unit_cost": 42000.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_3H",
        "condition": "NEW",
    },
    {
        "material_id": "MAT-PDC-600",
        "description": "PDC Bit 6\" (4-blade, 13mm cutters)",
        "material_group": "BITS",
        "unit": "EA",
        "stock_qty": 2,
        "min_stock": 2,
        "unit_cost": 28000.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_4H",
        "condition": "NEW",
    },
    # Drill Collars
    {
        "material_id": "MAT-DC-675",
        "description": "Drill Collar 6-3/4\" x 31 ft (non-mag, Monel)",
        "material_group": "BHA",
        "unit": "EA",
        "stock_qty": 6,
        "min_stock": 4,
        "unit_cost": 18500.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_3H",
        "condition": "GOOD",
    },
    {
        "material_id": "MAT-DC-475",
        "description": "Drill Collar 4-3/4\" x 31 ft (non-mag)",
        "material_group": "BHA",
        "unit": "EA",
        "stock_qty": 4,
        "min_stock": 3,
        "unit_cost": 12200.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_4H",
        "condition": "GOOD",
    },
    # MWD / LWD Tools
    {
        "material_id": "MAT-MWD-900",
        "description": "MWD Tool Assembly (pulser, directional, gamma)",
        "material_group": "MWD_LWD",
        "unit": "EA",
        "stock_qty": 2,
        "min_stock": 1,
        "unit_cost": 185000.00,
        "storage_location": "SLB Field Office",
        "well_assignment": "MIP_3H",
        "condition": "GOOD",
    },
    {
        "material_id": "MAT-LWD-910",
        "description": "LWD Resistivity / Density / Neutron Sub",
        "material_group": "MWD_LWD",
        "unit": "EA",
        "stock_qty": 1,
        "min_stock": 1,
        "unit_cost": 210000.00,
        "storage_location": "SLB Field Office",
        "well_assignment": "MIP_4H",
        "condition": "GOOD",
    },
    # Mud Motors
    {
        "material_id": "MAT-MM-675",
        "description": "Mud Motor 6-3/4\" (7/8 lobe, adjustable bend)",
        "material_group": "BHA",
        "unit": "EA",
        "stock_qty": 3,
        "min_stock": 2,
        "unit_cost": 32000.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_3H",
        "condition": "FAIR",
    },
    {
        "material_id": "MAT-MM-475",
        "description": "Mud Motor 4-3/4\" (5/6 lobe, fixed bend 1.5 deg)",
        "material_group": "BHA",
        "unit": "EA",
        "stock_qty": 2,
        "min_stock": 1,
        "unit_cost": 26000.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_4H",
        "condition": "NEW",
    },
    # Stabilizers
    {
        "material_id": "MAT-STB-850",
        "description": "String Stabilizer 8-1/2\" (integral blade, hardfaced)",
        "material_group": "BHA",
        "unit": "EA",
        "stock_qty": 5,
        "min_stock": 3,
        "unit_cost": 9800.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_3H",
        "condition": "FAIR",
    },
    {
        "material_id": "MAT-STB-600",
        "description": "Near-bit Stabilizer 6\" (replaceable sleeve)",
        "material_group": "BHA",
        "unit": "EA",
        "stock_qty": 3,
        "min_stock": 2,
        "unit_cost": 7500.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_4H",
        "condition": "GOOD",
    },
    # ESP Pump (for completion phase)
    {
        "material_id": "MAT-ESP-450",
        "description": "ESP Pump Assembly DN1750 (340-stage, 1500 BPD)",
        "material_group": "COMPLETION",
        "unit": "EA",
        "stock_qty": 1,
        "min_stock": 1,
        "unit_cost": 145000.00,
        "storage_location": "Baker Hughes Warehouse",
        "well_assignment": "MIP_3H",
        "condition": "NEW",
    },
    # Casing
    {
        "material_id": "MAT-CSG-700",
        "description": "Casing 7\" 26# P-110 BTC (production casing)",
        "material_group": "CASING",
        "unit": "JT",
        "stock_qty": 320,
        "min_stock": 280,
        "unit_cost": 485.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_3H",
        "condition": "NEW",
    },
    {
        "material_id": "MAT-CSG-958",
        "description": "Casing 9-5/8\" 40# L-80 BTC (surface casing)",
        "material_group": "CASING",
        "unit": "JT",
        "stock_qty": 55,
        "min_stock": 50,
        "unit_cost": 720.00,
        "storage_location": "MSEEL Pipe Yard",
        "well_assignment": "MIP_4H",
        "condition": "NEW",
    },
    # Mud Chemicals
    {
        "material_id": "MAT-CHM-BEN",
        "description": "Bentonite (Wyoming gel, 200-mesh)",
        "material_group": "CHEMICALS",
        "unit": "SX",
        "stock_qty": 480,
        "min_stock": 200,
        "unit_cost": 14.50,
        "storage_location": "MSEEL Mud Plant",
        "well_assignment": None,
        "condition": "NEW",
    },
    {
        "material_id": "MAT-CHM-BAR",
        "description": "Barite (API-grade, 4.20 SG)",
        "material_group": "CHEMICALS",
        "unit": "SX",
        "stock_qty": 1200,
        "min_stock": 500,
        "unit_cost": 12.80,
        "storage_location": "MSEEL Mud Plant",
        "well_assignment": None,
        "condition": "NEW",
    },
    {
        "material_id": "MAT-CHM-CMT",
        "description": "Cement Blend Class H (Halliburton ThermaLock)",
        "material_group": "CHEMICALS",
        "unit": "SX",
        "stock_qty": 350,
        "min_stock": 150,
        "unit_cost": 22.00,
        "storage_location": "MSEEL Mud Plant",
        "well_assignment": "MIP_4H",
        "condition": "NEW",
    },
    # Pump Liners & Consumables
    {
        "material_id": "MAT-PL-650",
        "description": "Mud Pump Liner 6-1/2\" (chrome, National 12-P-160)",
        "material_group": "CONSUMABLES",
        "unit": "EA",
        "stock_qty": 6,
        "min_stock": 4,
        "unit_cost": 1850.00,
        "storage_location": "MSEEL Rig Floor",
        "well_assignment": None,
        "condition": "NEW",
    },
    {
        "material_id": "MAT-SCR-420",
        "description": "Shaker Screen Composite 170 mesh (Derrick FLC-2000)",
        "material_group": "CONSUMABLES",
        "unit": "EA",
        "stock_qty": 24,
        "min_stock": 12,
        "unit_cost": 320.00,
        "storage_location": "MSEEL Rig Floor",
        "well_assignment": None,
        "condition": "NEW",
    },
]

# ---------------------------------------------------------------------------
# 3. Procurement  (SAP MM – Purchase Orders)
# ---------------------------------------------------------------------------
_PROCUREMENT: list[dict[str, Any]] = [
    {
        "po_id": "PO-4500081001",
        "vendor": "Halliburton",
        "material_id": "MAT-CHM-CMT",
        "material_desc": "Cement Blend Class H (ThermaLock) - 400 sacks",
        "qty": 400,
        "unit_cost": 22.00,
        "total": 8800.00,
        "status": "IN_TRANSIT",
        "eta": _dt(1),
        "delivery_location": "MSEEL Mud Plant",
    },
    {
        "po_id": "PO-4500081002",
        "vendor": "Schlumberger",
        "material_id": "MAT-MWD-900",
        "material_desc": "MWD Tool Assembly - replacement pulser unit",
        "qty": 1,
        "unit_cost": 185000.00,
        "total": 185000.00,
        "status": "ORDERED",
        "eta": _dt(5),
        "delivery_location": "SLB Field Office",
    },
    {
        "po_id": "PO-4500081003",
        "vendor": "NOV",
        "material_id": "MAT-PL-650",
        "material_desc": "Mud Pump Liners 6-1/2\" chrome (qty 8)",
        "qty": 8,
        "unit_cost": 1850.00,
        "total": 14800.00,
        "status": "DELIVERED",
        "eta": _dt(-2),
        "delivery_location": "MSEEL Rig Floor",
    },
    {
        "po_id": "PO-4500081004",
        "vendor": "Baker Hughes",
        "material_id": "MAT-PDC-850",
        "material_desc": "PDC Bit 8-1/2\" (5-blade, 16mm cutters) - qty 2",
        "qty": 2,
        "unit_cost": 42000.00,
        "total": 84000.00,
        "status": "IN_TRANSIT",
        "eta": _dt(2),
        "delivery_location": "MSEEL Pipe Yard",
    },
    {
        "po_id": "PO-4500081005",
        "vendor": "TechnipFMC",
        "material_id": "MAT-CSG-700",
        "material_desc": "Casing 7\" 26# P-110 BTC - 150 joints",
        "qty": 150,
        "unit_cost": 485.00,
        "total": 72750.00,
        "status": "ORDERED",
        "eta": _dt(8),
        "delivery_location": "MSEEL Pipe Yard",
    },
    {
        "po_id": "PO-4500081006",
        "vendor": "Halliburton",
        "material_id": "MAT-MM-675",
        "material_desc": "Mud Motor 6-3/4\" (7/8 lobe, adj bend) - rebuilt",
        "qty": 1,
        "unit_cost": 32000.00,
        "total": 32000.00,
        "status": "DELIVERED",
        "eta": _dt(-3),
        "delivery_location": "MSEEL Pipe Yard",
    },
    {
        "po_id": "PO-4500081007",
        "vendor": "Schlumberger",
        "material_id": "MAT-LWD-910",
        "material_desc": "LWD Resistivity/Density sub - recalibrated spare",
        "qty": 1,
        "unit_cost": 210000.00,
        "total": 210000.00,
        "status": "IN_TRANSIT",
        "eta": _dt(3),
        "delivery_location": "SLB Field Office",
    },
    {
        "po_id": "PO-4500081008",
        "vendor": "NOV",
        "material_id": "MAT-SCR-420",
        "material_desc": "Shaker Screens Derrick FLC-2000 170 mesh (qty 36)",
        "qty": 36,
        "unit_cost": 320.00,
        "total": 11520.00,
        "status": "INVOICED",
        "eta": _dt(-7),
        "delivery_location": "MSEEL Rig Floor",
    },
    {
        "po_id": "PO-4500081009",
        "vendor": "Baker Hughes",
        "material_id": "MAT-ESP-450",
        "material_desc": "ESP Pump Assembly DN1750 - MIP_3H completion",
        "qty": 1,
        "unit_cost": 145000.00,
        "total": 145000.00,
        "status": "ORDERED",
        "eta": _dt(30),
        "delivery_location": "Baker Hughes Warehouse",
    },
    {
        "po_id": "PO-4500081010",
        "vendor": "TechnipFMC",
        "material_id": "MAT-CSG-958",
        "material_desc": "Casing 9-5/8\" 40# L-80 BTC - 60 joints",
        "qty": 60,
        "unit_cost": 720.00,
        "total": 43200.00,
        "status": "DELIVERED",
        "eta": _dt(-10),
        "delivery_location": "MSEEL Pipe Yard",
    },
]

# ---------------------------------------------------------------------------
# 4. Vendor Contracts  (SAP MM – Outline Agreements)
# ---------------------------------------------------------------------------
_VENDOR_CONTRACTS: list[dict[str, Any]] = [
    {
        "contract_id": "CTR-5500010001",
        "vendor": "Schlumberger",
        "service": "Directional Drilling & MWD/LWD Services",
        "start_date": _dt(-45),
        "end_date": _dt(90),
        "daily_rate": 18500.00,
        "total_value": 2_497_500.00,
        "status": "ACTIVE",
    },
    {
        "contract_id": "CTR-5500010002",
        "vendor": "Halliburton",
        "service": "Cementing Services (surface & production casing)",
        "start_date": _dt(-30),
        "end_date": _dt(60),
        "daily_rate": 0.00,  # lump-sum per job
        "total_value": 385_000.00,
        "status": "ACTIVE",
    },
    {
        "contract_id": "CTR-5500010003",
        "vendor": "Precision Drilling",
        "service": "Rig Rental - PD 780 AC Triple (1500 HP)",
        "start_date": _dt(-60),
        "end_date": _dt(120),
        "daily_rate": 32000.00,
        "total_value": 5_760_000.00,
        "status": "ACTIVE",
    },
    {
        "contract_id": "CTR-5500010004",
        "vendor": "Baker Hughes",
        "service": "Completion Services & ESP Installation",
        "start_date": _dt(30),
        "end_date": _dt(90),
        "daily_rate": 0.00,  # lump-sum
        "total_value": 620_000.00,
        "status": "PLANNED",
    },
    {
        "contract_id": "CTR-5500010005",
        "vendor": "NOV",
        "service": "Rig Equipment Maintenance & Spare Parts Supply",
        "start_date": _dt(-60),
        "end_date": _dt(120),
        "daily_rate": 4500.00,
        "total_value": 810_000.00,
        "status": "ACTIVE",
    },
    {
        "contract_id": "CTR-5500010006",
        "vendor": "TechnipFMC",
        "service": "Wellhead & Casing Supply Agreement",
        "start_date": _dt(-90),
        "end_date": _dt(60),
        "daily_rate": 0.00,
        "total_value": 475_000.00,
        "status": "ACTIVE",
    },
    {
        "contract_id": "CTR-5500010007",
        "vendor": "Weatherford",
        "service": "Mud Logging & Gas Chromatography",
        "start_date": _dt(-45),
        "end_date": _dt(90),
        "daily_rate": 3200.00,
        "total_value": 432_000.00,
        "status": "ACTIVE",
    },
    {
        "contract_id": "CTR-5500010008",
        "vendor": "Schlumberger",
        "service": "Wireline Logging (open-hole suite, cased-hole CBL)",
        "start_date": _dt(15),
        "end_date": _dt(45),
        "daily_rate": 0.00,
        "total_value": 290_000.00,
        "status": "PLANNED",
    },
]

# ---------------------------------------------------------------------------
# 5. SAP PM Notifications  (QMEL table style)
# ---------------------------------------------------------------------------
_NOTIFICATIONS: list[dict[str, Any]] = [
    {
        "notif_id": "NOTIF-300101",
        "type": "M1",
        "well_id": "MIP_3H",
        "description": "PDC bit worn - ROP dropped below 25 ft/hr in lateral section",
        "priority": 1,
        "created": _dt(-2),
        "status": "IN_PROCESS",
    },
    {
        "notif_id": "NOTIF-300102",
        "type": "M2",
        "well_id": "MIP_3H",
        "description": "BHA run 4 exceeded planned footage - inspection required per policy",
        "priority": 2,
        "created": _dt(-1),
        "status": "OUTSTANDING",
    },
    {
        "notif_id": "NOTIF-300103",
        "type": "M1",
        "well_id": "MIP_3H",
        "description": "MWD azimuth offset >0.3 deg detected at 9,200 ft survey station",
        "priority": 2,
        "created": _dt(-1),
        "status": "OUTSTANDING",
    },
    {
        "notif_id": "NOTIF-300104",
        "type": "M1",
        "well_id": "MIP_3H",
        "description": "Mud motor stalled at 8,870 ft - differential sticking suspected",
        "priority": 1,
        "created": _dt(-6),
        "status": "COMPLETED",
    },
    {
        "notif_id": "NOTIF-300105",
        "type": "M3",
        "well_id": "MIP_3H",
        "description": "Scheduled shaker screen replacement due - vibrating screen #2 torn",
        "priority": 3,
        "created": _dt(-3),
        "status": "OUTSTANDING",
    },
    {
        "notif_id": "NOTIF-300106",
        "type": "M1",
        "well_id": "MIP_3H",
        "description": "#2 mud pump liner cracked - high-pressure washout on discharge side",
        "priority": 1,
        "created": _dt(-1),
        "status": "IN_PROCESS",
    },
    {
        "notif_id": "NOTIF-300107",
        "type": "M3",
        "well_id": "MIP_3H",
        "description": "Routine standpipe pressure gauge calibration (monthly)",
        "priority": 4,
        "created": _dt(-10),
        "status": "COMPLETED",
    },
    {
        "notif_id": "NOTIF-300108",
        "type": "M2",
        "well_id": "MIP_4H",
        "description": "ROP declining in curve build - bit dulling, recommend trip for bit change",
        "priority": 2,
        "created": _dt(0),
        "status": "OUTSTANDING",
    },
    {
        "notif_id": "NOTIF-300109",
        "type": "M1",
        "well_id": "MIP_4H",
        "description": "Stabilizer blade gauge wear >1/8\" - undergauge risk in 8.5\" hole",
        "priority": 2,
        "created": _dt(-3),
        "status": "IN_PROCESS",
    },
    {
        "notif_id": "NOTIF-300110",
        "type": "M2",
        "well_id": "MIP_4H",
        "description": "Mud weight increase required for curve section - kick tolerance review",
        "priority": 2,
        "created": _dt(-5),
        "status": "COMPLETED",
    },
]


# ===================================================================
# Public API
# ===================================================================

def get_work_orders() -> list[dict]:
    """Return all SAP PM work orders for MSEEL drilling operations."""
    return [dict(wo) for wo in _WORK_ORDERS]


def get_equipment_bom() -> list[dict]:
    """Return the drilling equipment Bill of Materials."""
    return [dict(item) for item in _EQUIPMENT_BOM]


def get_procurement() -> list[dict]:
    """Return active purchase orders for MSEEL drilling operations."""
    return [dict(po) for po in _PROCUREMENT]


def get_vendor_contracts() -> list[dict]:
    """Return vendor service contracts for rig operations."""
    return [dict(c) for c in _VENDOR_CONTRACTS]


def get_notifications() -> list[dict]:
    """Return recent SAP PM notifications."""
    return [dict(n) for n in _NOTIFICATIONS]


def get_sap_kpis() -> dict:
    """Return summary KPIs computed from the SAP mock data."""
    open_wos = sum(
        1 for wo in _WORK_ORDERS if wo["status"] in ("OPEN", "IN_PROGRESS")
    )
    overdue_wos = sum(
        1
        for wo in _WORK_ORDERS
        if wo["status"] in ("OPEN", "IN_PROGRESS")
        and wo["due_date"] < _BASE.strftime("%Y-%m-%d")
    )
    total_material_value = sum(
        item["stock_qty"] * item["unit_cost"] for item in _EQUIPMENT_BOM
    )
    active_contracts = sum(
        1 for c in _VENDOR_CONTRACTS if c["status"] == "ACTIVE"
    )
    pending_pos = sum(
        1 for po in _PROCUREMENT if po["status"] in ("ORDERED", "IN_TRANSIT")
    )
    return {
        "open_wos": open_wos,
        "overdue_wos": overdue_wos,
        "total_material_value": round(total_material_value, 2),
        "active_contracts": active_contracts,
        "pending_pos": pending_pos,
    }

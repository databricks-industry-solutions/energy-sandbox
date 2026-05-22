"""
Load physics-based production data into Databricks Delta tables.
Uses the same Arps/Darcy models as the app, writing real data to Unity Catalog.
"""

import json
import math
import subprocess
import sys
from datetime import datetime, timedelta

PROFILE = "fe-vm-oil-pump-monitor"
WH = "87e069097741b56c"
SCHEMA = "oil_pump_monitor_catalog.production_optimizer"


def run_sql(sql: str) -> dict:
    """Execute SQL via Databricks API."""
    payload = json.dumps({"statement": sql, "warehouse_id": WH, "wait_timeout": "30s"})
    result = subprocess.run(
        ["databricks", "api", "post", "/api/2.0/sql/statements",
         f"--profile={PROFILE}", "--json", payload],
        capture_output=True, text=True, timeout=90
    )
    try:
        d = json.loads(result.stdout)
        state = d.get("status", {}).get("state", "UNKNOWN")
        if state != "SUCCEEDED":
            print(f"  WARN: {state} — {d.get('status', {}).get('error', {}).get('message', '')[:100]}")
        return d
    except:
        print(f"  ERROR: {result.stderr[:200]}")
        return {}


# ── Seeded PRNG ──
def seeded_random(seed: int):
    s = seed
    def rng():
        nonlocal s
        s = (s * 16807) % 2147483647
        return (s - 1) / 2147483646
    return rng


# ── Arps decline ──
def arps_rate(qi, di, b, t):
    if b == 0:
        return qi * math.exp(-di * t)
    return qi / (1 + b * di * t) ** (1 / b)


# ── Well definitions (Delaware Basin CO2-EOR) ──
WELLS = [
    # Pattern A: Apache 5-spot
    {"id": "W-A01", "name": "Apache 1-A", "type": "producer", "pattern": "PAT-A", "pad": "PAD-A1",
     "oil": 190, "gas": 520, "water": 580, "wc": 0.55, "gor": 490, "co2": 5.2, "tp": 680, "cp": 920, "bhp": 2850},
    {"id": "W-A02", "name": "Apache 2-A", "type": "producer", "pattern": "PAT-A", "pad": "PAD-A1",
     "oil": 245, "gas": 680, "water": 420, "wc": 0.42, "gor": 510, "co2": 3.8, "tp": 720, "cp": 950, "bhp": 2920},
    {"id": "W-A03", "name": "Apache 3-A", "type": "producer", "pattern": "PAT-A", "pad": "PAD-A2",
     "oil": 155, "gas": 430, "water": 650, "wc": 0.63, "gor": 470, "co2": 7.1, "tp": 640, "cp": 880, "bhp": 2780},
    {"id": "W-A04", "name": "Apache 4-A", "type": "producer", "pattern": "PAT-A", "pad": "PAD-A2",
     "oil": 210, "gas": 590, "water": 510, "wc": 0.49, "gor": 500, "co2": 4.5, "tp": 700, "cp": 940, "bhp": 2880},
    {"id": "W-A05", "name": "Apache INJ-A", "type": "injector", "pattern": "PAT-A", "pad": "PAD-A1",
     "oil": 0, "gas": 0, "water": 0, "wc": 0, "gor": 0, "co2": 99.3, "tp": 0, "cp": 0, "bhp": 3200,
     "co2_inj": 2100},

    # Pattern B: Bravo inverted 5-spot
    {"id": "W-B01", "name": "Bravo 1-B", "type": "producer", "pattern": "PAT-B", "pad": "PAD-B1",
     "oil": 230, "gas": 640, "water": 490, "wc": 0.46, "gor": 530, "co2": 4.1, "tp": 710, "cp": 960, "bhp": 2950},
    {"id": "W-B02", "name": "Bravo 2-B", "type": "producer", "pattern": "PAT-B", "pad": "PAD-B1",
     "oil": 275, "gas": 760, "water": 380, "wc": 0.38, "gor": 550, "co2": 3.2, "tp": 740, "cp": 980, "bhp": 3010},
    {"id": "W-B03", "name": "Bravo 3-B", "type": "producer", "pattern": "PAT-B", "pad": "PAD-B2",
     "oil": 195, "gas": 540, "water": 560, "wc": 0.52, "gor": 480, "co2": 5.8, "tp": 670, "cp": 910, "bhp": 2830},
    {"id": "W-B04", "name": "Bravo 4-B", "type": "producer", "pattern": "PAT-B", "pad": "PAD-B2",
     "oil": 260, "gas": 720, "water": 440, "wc": 0.41, "gor": 540, "co2": 3.5, "tp": 730, "cp": 970, "bhp": 2990},
    {"id": "W-B05", "name": "Bravo INJ-B", "type": "injector", "pattern": "PAT-B", "pad": "PAD-B1",
     "oil": 0, "gas": 0, "water": 0, "wc": 0, "gor": 0, "co2": 99.5, "tp": 0, "cp": 0, "bhp": 3300,
     "co2_inj": 2400},

    # Pattern C: Charlie 5-spot
    {"id": "W-C01", "name": "Charlie 1-C", "type": "producer", "pattern": "PAT-C", "pad": "PAD-C1",
     "oil": 170, "gas": 470, "water": 710, "wc": 0.68, "gor": 460, "co2": 8.9, "tp": 620, "cp": 860, "bhp": 2720},
    {"id": "W-C02", "name": "Charlie 2-C", "type": "producer", "pattern": "PAT-C", "pad": "PAD-C1",
     "oil": 145, "gas": 400, "water": 780, "wc": 0.72, "gor": 450, "co2": 11.2, "tp": 590, "cp": 840, "bhp": 2680},
    {"id": "W-C03", "name": "Charlie 3-C", "type": "producer", "pattern": "PAT-C", "pad": "PAD-C1",
     "oil": 200, "gas": 550, "water": 600, "wc": 0.55, "gor": 490, "co2": 6.3, "tp": 680, "cp": 920, "bhp": 2840},
    {"id": "W-C04", "name": "Charlie 4-C", "type": "producer", "pattern": "PAT-C", "pad": "PAD-C1",
     "oil": 160, "gas": 440, "water": 730, "wc": 0.70, "gor": 465, "co2": 10.1, "tp": 610, "cp": 850, "bhp": 2700},
    {"id": "W-C05", "name": "Charlie INJ-C", "type": "injector", "pattern": "PAT-C", "pad": "PAD-C1",
     "oil": 0, "gas": 0, "water": 0, "wc": 0, "gor": 0, "co2": 99.1, "tp": 0, "cp": 0, "bhp": 3100,
     "co2_inj": 1800},

    # Pattern D: Delta inverted 5-spot
    {"id": "W-D01", "name": "Delta 1-D", "type": "producer", "pattern": "PAT-D", "pad": "PAD-D1",
     "oil": 285, "gas": 790, "water": 350, "wc": 0.35, "gor": 560, "co2": 2.8, "tp": 750, "cp": 990, "bhp": 3050},
    {"id": "W-D02", "name": "Delta 2-D", "type": "producer", "pattern": "PAT-D", "pad": "PAD-D1",
     "oil": 300, "gas": 830, "water": 320, "wc": 0.31, "gor": 580, "co2": 2.1, "tp": 770, "cp": 1010, "bhp": 3100},
    {"id": "W-D03", "name": "Delta 3-D", "type": "producer", "pattern": "PAT-D", "pad": "PAD-D1",
     "oil": 250, "gas": 700, "water": 410, "wc": 0.39, "gor": 540, "co2": 3.4, "tp": 730, "cp": 970, "bhp": 2980},
    {"id": "W-D04", "name": "Delta 4-D", "type": "producer", "pattern": "PAT-D", "pad": "PAD-D1",
     "oil": 270, "gas": 750, "water": 370, "wc": 0.36, "gor": 560, "co2": 2.9, "tp": 760, "cp": 1000, "bhp": 3040},
    {"id": "W-D05", "name": "Delta INJ-D", "type": "injector", "pattern": "PAT-D", "pad": "PAD-D1",
     "oil": 0, "gas": 0, "water": 0, "wc": 0, "gor": 0, "co2": 99.6, "tp": 0, "cp": 0, "bhp": 3400,
     "co2_inj": 2200},
]

PATTERNS = [
    {"id": "PAT-A", "name": "Apache 5-Spot", "type": "5-spot", "phase": "CO2_injection", "cycle": 5, "target_p": 3200, "current_p": 2950, "co2_slug": 45000, "water_slug": 32000, "bt": "2026-09-15"},
    {"id": "PAT-B", "name": "Bravo Inverted 5-Spot", "type": "inverted_5spot", "phase": "water_injection", "cycle": 4, "target_p": 3300, "current_p": 3100, "co2_slug": 52000, "water_slug": 38000, "bt": "2026-12-01"},
    {"id": "PAT-C", "name": "Charlie 5-Spot", "type": "5-spot", "phase": "CO2_injection", "cycle": 8, "target_p": 3100, "current_p": 3050, "co2_slug": 78000, "water_slug": 55000, "bt": "2026-06-20"},
    {"id": "PAT-D", "name": "Delta Inverted 5-Spot", "type": "inverted_5spot", "phase": "production", "cycle": 2, "target_p": 3400, "current_p": 3050, "co2_slug": 22000, "water_slug": 15000, "bt": "2027-04-10"},
]


def load_wells():
    print("Loading bronze_wells...")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for w in WELLS:
        rows.append(
            f"('{w['id']}', '{w['name']}', '{w['type']}', 'active', '{w['pattern']}', '{w['pad']}', "
            f"{w['oil']}, {w['gas']}, {w['water']}, {w.get('co2_inj', 0)}, {w.get('water_inj', 0)}, "
            f"65, {w['tp']}, {w['cp']}, {w['bhp']}, {w['co2']}, {w['gor']}, {w['wc']}, "
            f"'Delaware Wolfcamp', '{now}')"
        )
    sql = f"INSERT INTO {SCHEMA}.bronze_wells VALUES " + ",\n".join(rows)
    run_sql(sql)


def load_patterns():
    print("Loading bronze_patterns...")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for p in PATTERNS:
        rows.append(
            f"('{p['id']}', '{p['name']}', '{p['type']}', '{p['phase']}', {p['cycle']}, "
            f"{p['target_p']}, {p['current_p']}, {p['co2_slug']}, {p['water_slug']}, "
            f"'{p['bt']}', '{now}')"
        )
    sql = f"INSERT INTO {SCHEMA}.bronze_patterns VALUES " + ",\n".join(rows)
    run_sql(sql)


def load_production_history():
    print("Loading silver_production_history...")
    producers = [w for w in WELLS if w["type"] == "producer"]

    for idx, w in enumerate(producers):
        months_on = 24 + idx * 3
        seed = ord(w["id"][2]) * 1000 + ord(w["id"][-1])
        rng = seeded_random(seed)

        # Arps params
        b = 0.3 + rng() * 0.4
        di = 0.01 + rng() * 0.03
        qi = w["oil"] * (1 + b * di * months_on) ** (1 / b)

        initial_gor = w["gor"] * 0.6
        initial_wc = max(0.05, w["wc"] * 0.3)
        initial_co2 = max(0.5, w["co2"] * 0.1)
        initial_tp = w["tp"] * 1.3
        initial_cp = w["cp"] * 1.2
        initial_bhp = w["bhp"] * 1.15

        start_date = datetime.utcnow() - timedelta(days=months_on * 30)
        rows = []
        cum_oil, cum_gas, cum_water = 0, 0, 0

        for m in range(months_on + 1):
            t = m / months_on if months_on > 0 else 0
            oil_pred = arps_rate(qi, di, b, m)
            flood = 1 + 0.12 * math.sin(math.pi * (t - 0.3) / 0.4) if 0.3 < t < 0.7 else 1
            oil = max(5, oil_pred * (1 + (rng() - 0.5) * 0.1) * flood)

            gor = initial_gor + (w["gor"] - initial_gor) * t ** 0.8 + (rng() - 0.5) * 30
            gas = oil * max(100, gor) / 1000

            wc_base = initial_wc + (w["wc"] - initial_wc) / (1 + math.exp(-8 * (t - 0.5)))
            wc = min(0.95, max(0, wc_base + (rng() - 0.5) * 0.03))
            water = oil * wc / (1 - wc) if wc < 1 else oil * 10

            co2_base = initial_co2 * (1 + t) if t < 0.35 else initial_co2 + (w["co2"] - initial_co2) * ((t - 0.35) / 0.65) ** 1.5
            co2 = min(80, max(0, co2_base + (rng() - 0.5) * 1.5))

            p_decay = 1 - t * 0.25
            tp = max(100, initial_tp * p_decay + (rng() - 0.5) * 20)
            cp = max(200, initial_cp * p_decay + (rng() - 0.5) * 15)
            bhp = max(500, initial_bhp * (1 - t * 0.15) + (rng() - 0.5) * 30)

            cum_oil += oil * 30.44
            cum_gas += gas * 30.44
            cum_water += water * 30.44

            d = start_date + timedelta(days=m * 30)
            date_str = d.strftime("%Y-%m-%d")

            rows.append(
                f"('{w['id']}', '{w['name']}', {m}, '{date_str}', "
                f"{round(oil,1)}, {round(gas,1)}, {round(water,1)}, {round(wc,3)}, {round(gor,1)}, "
                f"{round(co2,1)}, {round(tp,1)}, {round(cp,1)}, {round(bhp,1)}, "
                f"{round(cum_oil)}, {round(cum_gas)}, {round(cum_water)})"
            )

        # Insert in batches of 20
        for i in range(0, len(rows), 20):
            batch = rows[i:i+20]
            sql = f"INSERT INTO {SCHEMA}.silver_production_history VALUES " + ",\n".join(batch)
            run_sql(sql)

        print(f"  {w['name']}: {len(rows)} months loaded")


def load_economics():
    print("Loading silver_economics...")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    producers = [w for w in WELLS if w["type"] == "producer"]
    total_oil = sum(w["oil"] for w in producers)

    rows = []
    for w in producers:
        oil_rev = w["oil"] * 72
        gas_rev = w["gas"] * 3.2
        co2_alloc = (w["oil"] / total_oil) * 9500 * 1.05 if total_oil > 0 else 0
        loe = w["oil"] * 8.5 + w["water"] * 0.45
        transport = w["oil"] * 2.5 + w["gas"] * 0.15
        boe = w["oil"] + w["gas"] / 6
        netback = (oil_rev + gas_rev - co2_alloc - loe - transport) / boe if boe > 0 else 0
        co2_boe = co2_alloc / boe if boe > 0 else 0

        rows.append(
            f"('{w['id']}', '{w['name']}', {round(oil_rev,2)}, {round(gas_rev,2)}, "
            f"{round(co2_alloc,2)}, {round(loe,2)}, {round(transport,2)}, "
            f"{round(netback,2)}, {round(co2_boe,2)}, '{now}')"
        )

    sql = f"INSERT INTO {SCHEMA}.silver_economics VALUES " + ",\n".join(rows)
    run_sql(sql)


def load_field_economics():
    print("Loading gold_field_economics...")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    producers = [w for w in WELLS if w["type"] == "producer"]
    total_oil = sum(w["oil"] for w in producers)
    total_gas = sum(w["gas"] for w in producers)
    total_water = sum(w["water"] for w in producers)
    total_boe = total_oil + total_gas / 6

    revenue = total_oil * 72 + total_gas * 3.2
    opex = total_oil * 8.5 + total_water * 0.45
    co2_cost = 9500 * 1.05
    transport = total_oil * 2.5 + total_gas * 0.15
    netback = (revenue - co2_cost - opex - transport) / total_boe if total_boe > 0 else 0
    breakeven = 38
    carbon_credits = 185 * 28.5  # tCO2/d * $/ton

    sql = (
        f"INSERT INTO {SCHEMA}.gold_field_economics VALUES "
        f"({round(revenue,2)}, {round(opex,2)}, {round(co2_cost,2)}, {round(transport,2)}, "
        f"{round(netback,2)}, {round(netback * 1.1,2)}, {breakeven}, {round(carbon_credits,2)}, "
        f"{round(total_boe,2)}, {len(producers)}, '{now}')"
    )
    run_sql(sql)


if __name__ == "__main__":
    print(f"Loading data into {SCHEMA}...")
    load_wells()
    load_patterns()
    load_production_history()
    load_economics()
    load_field_economics()
    print("\nDone! All tables loaded.")

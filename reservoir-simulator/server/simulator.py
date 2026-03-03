"""
Norne field reservoir simulation engine.

Models the Norne North Sea field (46×112×22 in the real Eclipse deck).
For interactive visualization, a representative 20×10×5 sub-grid is used.
Producers: B-2H, D-1H, E-3H, D-2H.  Injector: C-4H (gas/water).

Reference: Norne benchmark model, SPE ATW 2013.
Grid: METRIC units.  Initial pressure ~360 bar.
"""

import math
import random

# ---------------------------------------------------------------------------
# Grid dimensions (representative sub-grid of real Norne 46×112×22)
# ---------------------------------------------------------------------------
NI, NJ, NK = 20, 10, 5
TOTAL_CELLS = NI * NJ * NK

# ---------------------------------------------------------------------------
# Default wells — positions scaled from real Norne WELSPECS (1-indexed):
#   B-2H  → Norne i=15, j=31  →  vis i=5,  j=7
#   D-1H  → Norne i=22, j=22  →  vis i=9,  j=4
#   E-3H  → Norne i=12, j=72  →  vis i=5,  j=3
#   D-2H  → Norne i=14, j=28  →  vis i=15, j=3
#   C-4H  → Norne i=11, j=35  →  vis i=15, j=7  (gas injector)
# ---------------------------------------------------------------------------
WELLS = [
    {"name": "B-2H", "type": "PROD", "i": 5,  "j": 7},
    {"name": "D-1H", "type": "PROD", "i": 9,  "j": 4},
    {"name": "E-3H", "type": "PROD", "i": 5,  "j": 3},
    {"name": "D-2H", "type": "PROD", "i": 15, "j": 3},
    {"name": "C-4H", "type": "INJ",  "i": 15, "j": 7},
]

# ---------------------------------------------------------------------------
# Initial conditions (Norne Fangst/Ile formation, North Sea)
# ---------------------------------------------------------------------------
INIT_PRESSURE   = 360.0   # bar  (typical Norne initial reservoir pressure)
INIT_SO         = 0.68    # oil saturation
INIT_SW         = 0.27    # connate water saturation
INIT_SG         = 0.05    # initial gas saturation (above gas-oil contact)

TOTAL_TIMESTEPS = 40
DAYS_PER_STEP   = 91.25   # ~10 years / 40 steps


def _cell_index(i: int, j: int, k: int) -> int:
    return k * NI * NJ + j * NI + i


def _distance_to_nearest_producer(i: int, j: int, wells: list) -> float:
    dmin = 9999.0
    for w in wells:
        if w.get("type", "PROD") != "INJ":
            d = math.sqrt((i - w["i"]) ** 2 + (j - w["j"]) ** 2)
            if d < dmin:
                dmin = d
    return max(dmin, 0.5)


def _distance_to_nearest_injector(i: int, j: int, wells: list) -> float:
    dmin = 9999.0
    for w in wells:
        if w.get("type") == "INJ":
            d = math.sqrt((i - w["i"]) ** 2 + (j - w["j"]) ** 2)
            if d < dmin:
                dmin = d
    return max(dmin, 0.5)


def _init_grid() -> list:
    """Create initial Norne grid state."""
    cells = []
    for k in range(NK):
        for j in range(NJ):
            for i in range(NI):
                # Vary initial pressure slightly by depth (hydrostatic)
                depth_p = INIT_PRESSURE + k * 2.0
                # Add slight lateral heterogeneity (permeability variation)
                het = 0.98 + 0.04 * math.sin(i * 0.8) * math.cos(j * 0.7)
                cells.append({
                    "i": i, "j": j, "k": k,
                    "pressure": round(depth_p * het, 2),
                    "so": INIT_SO,
                    "sw": INIT_SW,
                    "sg": INIT_SG,
                })
    return cells


def _advance_timestep(cells: list, timestep: int, rng: random.Random,
                      wells: list = None) -> list:
    """
    Advance Norne grid by one timestep. Returns changed cells (sparse).
    Producers deplete pressure/oil.  Injector (C-4H) supports pressure.
    """
    if wells is None:
        wells = WELLS
    changed = []
    t_frac = timestep / TOTAL_TIMESTEPS

    has_injector = any(w.get("type") == "INJ" for w in wells)

    for cell in cells:
        i, j, k = cell["i"], cell["j"], cell["k"]
        d_prod = _distance_to_nearest_producer(i, j, wells)
        d_inj  = _distance_to_nearest_injector(i, j, wells) if has_injector else 9999.0

        # ── Pressure ───────────────────────────────────────────────────────
        # Decline near producers
        base_decline = 2.8 + 1.2 * math.exp(-d_prod / 4.0)
        noise = rng.gauss(0, 0.25)
        depth_factor = 1.0 - 0.04 * k
        p_decline = (base_decline + noise) * depth_factor

        # Injection support: pressure maintenance near C-4H
        if has_injector:
            inj_support = 1.5 * math.exp(-d_inj / 5.0) * (1 - math.exp(-t_frac * 3))
            p_decline = max(0.1, p_decline - inj_support)

        new_pressure = max(120.0, cell["pressure"] - p_decline)

        # ── Oil saturation ─────────────────────────────────────────────────
        proximity_prod = math.exp(-d_prod / 5.0)
        so_decline = 0.010 * proximity_prod * (1 + 0.25 * t_frac) + rng.gauss(0, 0.0008)
        so_decline = max(0.0, so_decline)
        new_so = max(0.12, cell["so"] - so_decline)

        # ── Water saturation ───────────────────────────────────────────────
        # Water breakthrough near injector over time
        if has_injector:
            inj_wt = math.exp(-d_inj / 6.0) * t_frac * 0.8
        else:
            inj_wt = 0.0
        sw_increase = so_decline * 0.80 + inj_wt * 0.015 + rng.gauss(0, 0.0004)
        new_sw = min(0.80, cell["sw"] + sw_increase)

        # ── Gas saturation ─────────────────────────────────────────────────
        # Gas comes out of solution below bubble point (~250 bar for Norne)
        bubble_pt = 250.0
        if new_pressure < bubble_pt:
            sg_increase = 0.004 * (bubble_pt - new_pressure) / bubble_pt * proximity_prod
        else:
            sg_increase = 0.0
        new_sg = max(0.0, min(0.30, 1.0 - new_so - new_sw))

        # Normalize
        total_s = new_so + new_sw + new_sg
        if total_s > 0:
            new_so = new_so / total_s
            new_sw = new_sw / total_s
            new_sg = new_sg / total_s

        dp   = abs(new_pressure - cell["pressure"])
        dso  = abs(new_so - cell["so"])
        dsw  = abs(new_sw - cell["sw"])

        cell["pressure"] = round(new_pressure, 2)
        cell["so"]       = round(new_so, 4)
        cell["sw"]       = round(new_sw, 4)
        cell["sg"]       = round(new_sg, 4)

        if dp > 0.1 or dso > 0.001 or dsw > 0.001:
            changed.append({
                "i": i, "j": j, "k": k,
                "pressure": cell["pressure"],
                "so":       cell["so"],
                "sw":       cell["sw"],
                "sg":       cell["sg"],
            })

    return changed


def compute_well_production(timestep: int, rng: random.Random,
                            cells: list, wells: list = None) -> list:
    """Compute per-well production for Norne producers (skip injectors)."""
    if wells is None:
        wells = WELLS
    results = []
    day = timestep * DAYS_PER_STEP

    for w in wells:
        if w.get("type") == "INJ":
            continue  # injectors don't produce

        wi, wj = w["i"], w["j"]
        pressures, so_vals, sw_vals = [], [], []

        for dk in range(NK):
            for di in range(-1, 2):
                for dj in range(-1, 2):
                    ci = max(0, min(NI - 1, wi + di))
                    cj = max(0, min(NJ - 1, wj + dj))
                    idx = _cell_index(ci, cj, dk)
                    pressures.append(cells[idx]["pressure"])
                    so_vals.append(cells[idx]["so"])
                    sw_vals.append(cells[idx]["sw"])

        avg_p  = sum(pressures) / len(pressures)
        avg_so = sum(so_vals) / len(so_vals)
        avg_sw = sum(sw_vals) / len(sw_vals)

        # ── Norne-calibrated production rates (METRIC: Sm³/day) ─────────
        # Average Norne plateau: ~250 Sm³/day oil per well
        base_oil = 240.0 + rng.gauss(0, 12.0)
        oil_rate = max(3.0,
            base_oil
            * (avg_p / INIT_PRESSURE)
            * (avg_so / INIT_SO)
            * (1.0 - 0.28 * (timestep / TOTAL_TIMESTEPS))
        )

        # Norne GOR: ~400–700 Sm³/Sm³ (rich gas condensate, DISGAS)
        gor_base = 480.0 + 150.0 * max(0.0, (250.0 - avg_p) / 250.0)
        gas_rate = oil_rate * gor_base / 1000.0  # MSm³/day → keep in "MSCF-equivalent" for economics

        # Water: increases with time and proximity to injector
        base_water = 15.0 + rng.gauss(0, 4.0)
        water_rate = max(0.0,
            base_water * (avg_sw / INIT_SW) * (1.0 + 1.8 * (timestep / TOTAL_TIMESTEPS))
        )

        bhp = max(100.0, avg_p - 45.0 - 18.0 * (timestep / TOTAL_TIMESTEPS))

        results.append({
            "well_name":         w["name"],
            "day":               round(day, 1),
            "timestep":          timestep,
            "oil_rate_stbd":     round(oil_rate, 1),
            "gas_rate_mscfd":    round(gas_rate, 1),
            "water_rate_stbd":   round(water_rate, 1),
            "bhp_bar":           round(bhp, 1),
            "avg_pressure_bar":  round(avg_p, 1),
            "avg_so":            round(avg_so, 4),
            "avg_sw":            round(avg_sw, 4),
            "cum_oil_stb":       0,   # computed externally
            "cum_gas_mscf":      0,
            "cum_water_stb":     0,
        })

    return results


def compute_field_summary(well_results: list) -> dict:
    """Aggregate Norne well results into field totals."""
    if not well_results:
        return {
            "field_oil_rate_stbd":   0.0,
            "field_gas_rate_mscfd":  0.0,
            "field_water_rate_stbd": 0.0,
            "field_liquid_rate_stbd": 0.0,
            "field_avg_bhp_bar":     0.0,
            "field_avg_pressure_bar": 0.0,
            "water_cut_pct":         0.0,
            "gor_scf_bbl":           0.0,
        }
    total_oil   = sum(w["oil_rate_stbd"]   for w in well_results)
    total_gas   = sum(w["gas_rate_mscfd"]  for w in well_results)
    total_water = sum(w["water_rate_stbd"] for w in well_results)
    avg_bhp     = sum(w["bhp_bar"]         for w in well_results) / len(well_results)
    avg_p       = sum(w["avg_pressure_bar"] for w in well_results) / len(well_results)

    return {
        "field_oil_rate_stbd":    round(total_oil,   1),
        "field_gas_rate_mscfd":   round(total_gas,   1),
        "field_water_rate_stbd":  round(total_water, 1),
        "field_liquid_rate_stbd": round(total_oil + total_water, 1),
        "field_avg_bhp_bar":      round(avg_bhp, 1),
        "field_avg_pressure_bar": round(avg_p,   1),
        "water_cut_pct":  round(total_water / max(total_oil + total_water, 1) * 100, 1),
        "gor_scf_bbl":    round(total_gas * 1000 / max(total_oil, 1), 0),
    }

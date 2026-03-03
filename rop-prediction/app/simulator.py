"""
Drilling Simulator — physics-based parameter simulation for MSEEL Marcellus Shale wells.
Live-streaming mode: 3s refresh, 30-tick loop with cycle-driven drilling events.

Wells: MIP_3H and MIP_4H (MSEEL — Marcellus Shale Energy and Environment Laboratory)

Cycle map (tick % 30):
   0– 7  MIP_3H normal drilling, good ROP
   8–12  MIP_3H high MSE event (bit wear)
  13–17  MIP_4H stuck pipe risk (low ROP, high torque)
  18–22  Both wells normal drilling
  23–27  MIP_3H inefficient drilling (high rop_gap)
  28–29  Recovery / transition
"""
from __future__ import annotations
import math
import random
from datetime import datetime
from typing import List, Dict, Any

WELLS = [
    {
        "well_id": "MIP_3H",
        "name": "MIP-3H",
        "field": "MSEEL Marcellus",
        "base_md_ft": 8000,
        "base_rop": 75,
        "base_wob": 28,
        "base_rpm": 130,
        "base_torque": 8000,
        "base_spp": 3200,
        "base_flow": 550,
        "base_hookload": 220,
    },
    {
        "well_id": "MIP_4H",
        "name": "MIP-4H",
        "field": "MSEEL Marcellus",
        "base_md_ft": 8200,
        "base_rop": 68,
        "base_wob": 32,
        "base_rpm": 120,
        "base_torque": 9000,
        "base_spp": 3400,
        "base_flow": 520,
        "base_hookload": 240,
    },
]

# Cycle-driven event windows within tick % 30
_CYCLE_EVENTS = {
    "normal_3h":        (0,  7),    # MIP_3H good ROP drilling
    "high_mse_3h":      (8,  12),   # MIP_3H bit wear / high MSE
    "stuck_pipe_4h":    (13, 17),   # MIP_4H stuck pipe risk
    "normal_both":      (18, 22),   # Both wells normal
    "inefficient_3h":   (23, 27),   # MIP_3H inefficient drilling
    "recovery":         (28, 29),   # Transition / recovery
}


def _g(mu: float, sigma: float, rng: random.Random) -> float:
    """Gaussian noise helper with explicit RNG."""
    return rng.gauss(mu, sigma)


def _cycle_intensity(cycle: int, start: int, end: int) -> float:
    """Return 0-1 sine envelope for cycle events (peaks at midpoint of window)."""
    if start <= cycle <= end:
        return math.sin(((cycle - start) / max(end - start, 1)) * math.pi)
    return 0.0


def _in_window(cycle: int, start: int, end: int) -> bool:
    """Check whether the cycle step is inside a given event window."""
    return start <= cycle <= end


def _simulate_well(well: Dict[str, Any], tick: int) -> Dict[str, Any]:
    """Simulate drilling parameters for a single well at a given tick."""
    # Deterministic RNG seeded by (well_id hash + tick) for reproducibility
    seed = hash(well["well_id"]) + tick
    rng = random.Random(seed)

    well_id = well["well_id"]
    cycle = tick % 30
    phi = (cycle / 30.0) * 2.0 * math.pi   # phase for sinusoidal oscillation

    # ── Measured depth: slowly increasing (simulates active drilling) ────────
    # ~2 ft per tick average advance, with sinusoidal wobble
    md = well["base_md_ft"] + tick * 2.0 + 5.0 * math.sin(phi)
    tvd = md * 0.85  # horizontal well approximation

    # ── Base values with sinusoidal oscillation + Gaussian noise ─────────────
    rop_actual = _g(well["base_rop"] + 12.0 * math.sin(phi), 4.0, rng)
    wob        = _g(well["base_wob"] + 3.0 * math.sin(phi + 0.8), 1.5, rng)
    rpm        = _g(well["base_rpm"] + 8.0 * math.sin(phi + 1.2), 3.0, rng)
    torque     = _g(well["base_torque"] + 800.0 * math.sin(phi + 0.5), 400.0, rng)
    spp        = _g(well["base_spp"] + 200.0 * math.cos(phi), 100.0, rng)
    flow       = _g(well["base_flow"] + 40.0 * math.sin(phi + 1.8), 20.0, rng)
    hookload   = _g(well["base_hookload"] + 15.0 * math.sin(phi + 2.0), 8.0, rng)

    # MSE via Teale equation: MSE = (480*T*N)/(D^2*ROP) + (4*WOB)/(pi*D^2)
    # T in ft-lbs, N in RPM, D in inches, ROP in ft/hr, WOB in lbs → psi
    bit_diameter = 8.75  # inches, typical for horizontal Marcellus lateral
    d2 = bit_diameter ** 2
    wob_lbs = abs(wob) * 1000.0  # klbs → lbs
    mse_base = (480.0 * abs(torque) * abs(rpm)) / (d2 * max(abs(rop_actual), 1.0)) \
             + (4.0 * wob_lbs) / (math.pi * d2)
    mse = _g(mse_base, 5000.0, rng)

    # ROP prediction: tracks actual with small offset and slight lag
    pred_offset = _g(3.0 + 2.0 * math.sin(phi * 0.7), 1.5, rng)
    rop_pred = rop_actual + pred_offset

    # Default status and hazard
    status = "DRILLING"
    hazard_flag = "NORMAL"

    # ── Event injection: MIP_3H high MSE (bit wear) ─────────────────────────
    if well_id == "MIP_3H" and _in_window(cycle, 8, 12):
        intensity = _cycle_intensity(cycle, 8, 12)
        # Bit wear: MSE spikes, ROP drops, torque rises
        mse        += intensity * 60000.0
        rop_actual -= intensity * 35.0
        torque     += intensity * 5000.0
        wob        += intensity * 6.0
        hazard_flag = "HIGH_MSE"

    # ── Event injection: MIP_4H stuck pipe risk ─────────────────────────────
    if well_id == "MIP_4H" and _in_window(cycle, 13, 17):
        intensity = _cycle_intensity(cycle, 13, 17)
        # Stuck pipe: ROP drops to near zero, torque spikes, hookload rises
        rop_actual -= intensity * 55.0
        torque     += intensity * 8000.0
        hookload   += intensity * 60.0
        spp        += intensity * 500.0
        wob        += intensity * 8.0
        hazard_flag = "STUCK_PIPE"
        if intensity > 0.7:
            status = "CIRCULATING"  # crew attempts to free pipe

    # ── Event injection: MIP_3H inefficient drilling ─────────────────────────
    if well_id == "MIP_3H" and _in_window(cycle, 23, 27):
        intensity = _cycle_intensity(cycle, 23, 27)
        # Inefficient: model predicts higher ROP than actual (big gap)
        rop_actual -= intensity * 25.0
        rop_pred   += intensity * 15.0
        mse        += intensity * 35000.0
        hazard_flag = "INEFFICIENT_DRILLING"

    # ── Normal good-ROP window: MIP_3H gets a slight boost ──────────────────
    if well_id == "MIP_3H" and _in_window(cycle, 0, 7):
        intensity = _cycle_intensity(cycle, 0, 7)
        rop_actual += intensity * 15.0
        mse        -= intensity * 15000.0
        if intensity > 0.5:
            hazard_flag = "OPTIMAL"

    # ── Connection event: brief pause every ~10 ticks for both wells ────────
    if cycle in (9, 19, 29) and rng.random() < 0.4:
        status = "CONNECTION"
        rop_actual *= 0.1   # near-zero ROP during connection
        rop_pred   *= 0.3

    # ── Tripping event: rare, signals bit change ────────────────────────────
    if well_id == "MIP_3H" and cycle == 12:
        status = "TRIPPING"
        rop_actual = _g(2.0, 1.0, rng)
        rop_pred   = _g(5.0, 1.5, rng)

    # ── Recalculate rop_pred after events (keep tracking with offset) ───────
    # Only adjust if status is still DRILLING and we haven't already tweaked
    if status == "DRILLING" and hazard_flag not in ("INEFFICIENT_DRILLING",):
        rop_pred = rop_actual + _g(3.0, 1.5, rng)

    # ── 5% random micro-spike (live streaming noise) ────────────────────────
    if rng.random() < 0.05:
        spike = rng.randint(0, 4)
        if spike == 0:
            torque   += rng.uniform(2000, 5000)
        elif spike == 1:
            spp      += rng.uniform(200, 500)
        elif spike == 2:
            mse      += rng.uniform(10000, 30000)
        elif spike == 3:
            hookload += rng.uniform(20, 50)
        else:
            rop_actual -= rng.uniform(10, 25)

    # ── Clamp to physical limits ────────────────────────────────────────────
    rop_actual = max(0.5, min(120.0, rop_actual))
    rop_pred   = max(0.5, min(140.0, rop_pred))
    mse        = max(30000.0, min(180000.0, mse))
    wob        = max(15.0, min(45.0, wob))
    rpm        = max(80.0, min(180.0, rpm))
    torque     = max(5000.0, min(25000.0, torque))
    spp        = max(2000.0, min(4500.0, spp))
    flow       = max(400.0, min(700.0, flow))
    hookload   = max(100.0, min(350.0, hookload))
    md         = max(well["base_md_ft"], md)

    # ── Derived metrics ─────────────────────────────────────────────────────
    rop_gap    = rop_pred - rop_actual
    efficiency = (rop_actual / max(rop_pred, 0.1)) * 100.0
    efficiency = max(10.0, min(150.0, efficiency))

    # ── Hazard flag override based on computed values ───────────────────────
    if hazard_flag == "NORMAL":
        if mse > 140000:
            hazard_flag = "HIGH_MSE"
        elif efficiency < 65:
            hazard_flag = "INEFFICIENT_DRILLING"
        elif efficiency > 95:
            hazard_flag = "OPTIMAL"

    return {
        "well_id":     well["well_id"],
        "name":        well["name"],
        "field":       well["field"],
        "rop_actual":  round(rop_actual, 1),
        "rop_pred":    round(rop_pred, 1),
        "rop_gap":     round(rop_gap, 1),
        "mse":         round(mse, 0),
        "wob":         round(wob, 1),
        "rpm":         round(rpm, 0),
        "torque":      round(torque, 0),
        "spp":         round(spp, 0),
        "flow":        round(flow, 0),
        "hookload":    round(hookload, 1),
        "md":          round(md, 1),
        "tvd":         round(tvd, 1),
        "hazard_flag": hazard_flag,
        "efficiency":  round(efficiency, 1),
        "status":      status,
        "cycle":       cycle,
        "simulated_at": datetime.utcnow().isoformat(),
    }


def simulate_all_wells(tick: int) -> List[Dict[str, Any]]:
    """Simulate both MSEEL wells and return list of well data dicts."""
    results = []
    for well in WELLS:
        record = _simulate_well(well, tick)
        results.append(record)
    return results

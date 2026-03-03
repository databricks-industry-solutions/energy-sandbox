import json
import math
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from ..db import db
from .simulate import _field_summaries, _well_timeseries

router = APIRouter()


class EconomicsRequest(BaseModel):
    run_id: str
    oil_price: float = 75.0
    gas_price: float = 2.80
    discount_rate: float = 0.10
    opex_per_boe: float = 8.50
    capex_per_well: float = 8000000.0


def _compute_economics(summaries: list, oil_price: float, gas_price: float,
                       discount_rate: float, opex_per_boe: float,
                       capex_per_well: float, num_wells: int = 4) -> dict:
    """Compute NPV, IRR, payback year, and cashflows from field summary data."""
    if not summaries:
        return {"npv_usd": 0, "irr": 0, "payback_year": 0, "cashflows": []}

    total_capex = capex_per_well * num_wells
    days_per_step = 91.25
    cashflows = []
    cum_npv = 0.0
    cum_undiscounted = -total_capex
    payback_year = 0
    payback_found = False

    # Group summaries by year (4 timesteps per year ~= 365 days)
    yearly = {}
    for s in summaries:
        year = int(s["day"] / 365) + 1
        if year not in yearly:
            yearly[year] = {"oil_stb": 0, "gas_mscf": 0, "water_stb": 0, "liquid_stb": 0}
        yearly[year]["oil_stb"] += s["field_oil_rate_stbd"] * days_per_step
        yearly[year]["gas_mscf"] += s["field_gas_rate_mscfd"] * days_per_step
        yearly[year]["water_stb"] += s["field_water_rate_stbd"] * days_per_step
        yearly[year]["liquid_stb"] += s["field_liquid_rate_stbd"] * days_per_step

    # Year 0: CAPEX only
    cashflows.append({
        "year": 0,
        "revenue": 0,
        "opex": 0,
        "capex": round(total_capex, 0),
        "net_cashflow": round(-total_capex, 0),
        "discounted_cf": round(-total_capex, 0),
        "cum_npv": round(-total_capex, 0),
    })
    cum_npv = -total_capex

    undiscounted_cfs = [-total_capex]

    for year in sorted(yearly.keys()):
        data = yearly[year]
        oil_revenue = data["oil_stb"] * oil_price
        gas_revenue = data["gas_mscf"] * gas_price
        revenue = oil_revenue + gas_revenue

        # BOE: oil + gas/6 (1 BOE = 6 MSCF)
        boe = data["oil_stb"] + data["gas_mscf"] / 6
        opex = boe * opex_per_boe

        net_cf = revenue - opex
        discount_factor = (1 + discount_rate) ** year
        discounted_cf = net_cf / discount_factor
        cum_npv += discounted_cf

        cum_undiscounted += net_cf
        if not payback_found and cum_undiscounted >= 0:
            payback_year = year
            payback_found = True

        undiscounted_cfs.append(net_cf)

        cashflows.append({
            "year": year,
            "revenue": round(revenue, 0),
            "opex": round(opex, 0),
            "capex": 0,
            "net_cashflow": round(net_cf, 0),
            "discounted_cf": round(discounted_cf, 0),
            "cum_npv": round(cum_npv, 0),
        })

    # Compute IRR using Newton's method
    irr = _compute_irr(undiscounted_cfs)

    if not payback_found:
        payback_year = len(yearly) + 1

    return {
        "npv_usd": round(cum_npv, 0),
        "irr": round(irr, 4) if irr is not None else 0,
        "payback_year": payback_year,
        "total_revenue": round(sum(c["revenue"] for c in cashflows), 0),
        "total_opex": round(sum(c["opex"] for c in cashflows), 0),
        "total_capex": round(total_capex, 0),
        "cashflows": cashflows,
    }


def _compute_irr(cashflows: list, max_iter: int = 100, tol: float = 1e-6) -> Optional[float]:
    """Compute IRR using Newton-Raphson method."""
    if not cashflows or len(cashflows) < 2:
        return None

    rate = 0.15  # initial guess
    for _ in range(max_iter):
        npv = 0
        d_npv = 0
        for t, cf in enumerate(cashflows):
            npv += cf / (1 + rate) ** t
            if t > 0:
                d_npv -= t * cf / (1 + rate) ** (t + 1)

        if abs(d_npv) < 1e-12:
            break
        new_rate = rate - npv / d_npv
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate

        # Guard against divergence
        if rate < -0.99 or rate > 10:
            return None

    return rate if -0.99 < rate < 10 else None


@router.post("/economics")
async def compute_economics(req: EconomicsRequest):
    summaries = _field_summaries.get(req.run_id, [])
    if not summaries:
        return {"error": "No simulation data for this run. Run a simulation first."}

    result = _compute_economics(
        summaries,
        oil_price=req.oil_price,
        gas_price=req.gas_price,
        discount_rate=req.discount_rate,
        opex_per_boe=req.opex_per_boe,
        capex_per_well=req.capex_per_well,
    )

    await db.execute(
        "INSERT INTO economics_results "
        "(run_id, scenario_id, oil_price, gas_price, discount_rate, opex_per_boe, "
        "capex_per_well, npv_usd, irr, payback_year, cashflows) "
        "VALUES (?, (SELECT scenario_id FROM simulation_runs WHERE id=?), "
        "?, ?, ?, ?, ?, ?, ?, ?, ?)",
        req.run_id, req.run_id, req.oil_price, req.gas_price, req.discount_rate,
        req.opex_per_boe, req.capex_per_well,
        float(result["npv_usd"]), float(result.get("irr") or 0),
        result["payback_year"], json.dumps(result["cashflows"]),
    )

    return result


@router.get("/economics/{run_id}")
async def get_economics(run_id: str):
    row = await db.fetchrow(
        "SELECT * FROM economics_results WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
        run_id,
    )
    if row:
        if isinstance(row.get("cashflows"), str):
            row["cashflows"] = json.loads(row["cashflows"])
        return row
    return {"error": "No economics results for this run"}

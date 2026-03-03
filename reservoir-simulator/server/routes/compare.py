import json
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import db
from .simulate import _field_summaries, _well_timeseries, _costs_cache, _operations_cache
from ..costs import compute_lifting_costs

router = APIRouter()


class CompareRequest(BaseModel):
    run_ids: list[str]


@router.post("/compare")
async def compare_runs(req: CompareRequest):
    """Compare production, NPV, lifting cost across multiple runs."""
    results = []
    for rid in req.run_ids[:6]:  # cap at 6 runs
        run = await db.fetchrow(
            "SELECT r.id, r.scenario_id, r.status, r.progress, "
            "s.name as scenario_name, s.deck_id "
            "FROM simulation_runs r LEFT JOIN scenarios s ON r.scenario_id = s.id "
            "WHERE r.id=?", rid,
        )
        if not run or run["status"] != "SUCCEEDED":
            continue

        summaries = _field_summaries.get(rid, [])
        series = _well_timeseries.get(rid, [])
        costs = _costs_cache.get(rid, {})

        # Production totals
        cum_oil = 0
        cum_gas = 0
        cum_water = 0
        peak_oil = 0
        if summaries:
            last = summaries[-1]
            cum_oil = last.get("cum_oil_stb", 0)
            cum_gas = last.get("cum_gas_mscf", 0)
            cum_water = last.get("cum_water_stb", 0)
            peak_oil = max(s["field_oil_rate_stbd"] for s in summaries)

        # Economics (default to 0 when missing so frontend never receives null)
        econ = await db.fetchrow(
            "SELECT npv_usd, irr, payback_year, oil_price, discount_rate "
            "FROM economics_results WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
            rid,
        )
        npv_val = (econ["npv_usd"] if econ and econ["npv_usd"] is not None else 0)
        irr_val = (econ["irr"] if econ and econ["irr"] is not None else 0)
        payback_val = (econ["payback_year"] if econ and econ["payback_year"] is not None else 0)

        # Lifting costs
        lifting = {}
        if costs and series:
            lifting = compute_lifting_costs(costs.get("well_costs", {}), series)

        total_boe = cum_oil + cum_gas / 6
        total_cost = costs.get("total_cost_usd", 0)
        avg_lifting = 0
        if lifting:
            lvals = [v["lifting_cost_per_boe"] for v in lifting.values() if v["lifting_cost_per_boe"] > 0]
            avg_lifting = sum(lvals) / len(lvals) if lvals else 0

        # Production profile for chart
        profile = []
        for s in summaries:
            profile.append({
                "day": s["day"],
                "oil_rate": s["field_oil_rate_stbd"],
                "water_cut": s["water_cut_pct"],
                "pressure": s["field_avg_pressure_bar"],
            })

        results.append({
            "run_id": rid,
            "scenario_name": run["scenario_name"],
            "deck_id": run["deck_id"],
            "cum_oil_stb": round(cum_oil),
            "cum_gas_mscf": round(cum_gas),
            "cum_water_stb": round(cum_water),
            "cum_boe": round(total_boe),
            "peak_oil_rate": round(peak_oil, 1),
            "npv_usd": npv_val,
            "irr": irr_val,
            "payback_year": payback_val,
            "total_cost_usd": round(total_cost),
            "avg_lifting_cost_boe": round(avg_lifting, 2),
            "full_cycle_cost_boe": round(total_cost / total_boe, 2) if total_boe else 0,
            "num_operations": len(_operations_cache.get(rid, [])),
            "profile": profile,
            "lifting_by_well": lifting,
        })

    return {"runs": results, "count": len(results)}

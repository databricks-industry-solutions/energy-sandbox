import json
from fastapi import APIRouter
from .simulate import _well_timeseries, _costs_cache
from ..db import db
from ..costs import (
    SAP_MATERIALS, SAP_SERVICES, SAP_EQUIPMENT,
    estimate_full_cycle_costs, compute_lifting_costs,
)

router = APIRouter()


@router.get("/costs/{run_id}")
async def get_costs(run_id: str):
    """Full-cycle cost breakdown for a completed run."""
    costs = _costs_cache.get(run_id)
    if costs is not None:
        return {"run_id": run_id, **costs}

    row = await db.fetchrow(
        "SELECT costs FROM run_costs WHERE run_id=?", run_id,
    )
    if row and row.get("costs"):
        costs = json.loads(row["costs"])
        _costs_cache[run_id] = costs
        return {"run_id": run_id, **costs}

    return {"run_id": run_id, "total_cost_usd": 0,
            "message": "No cost data. Run a simulation first."}


@router.get("/costs/{run_id}/lifting")
async def get_lifting_costs(run_id: str):
    """Lifting cost per BOE per well."""
    costs = _costs_cache.get(run_id)
    series = _well_timeseries.get(run_id, [])
    if not costs or not series:
        return {"run_id": run_id, "lifting_costs": {},
                "message": "No data available."}
    lifting = compute_lifting_costs(costs["well_costs"], series)
    return {"run_id": run_id, "lifting_costs": lifting}


@router.get("/sap/materials")
async def get_sap_materials():
    """SAP material master (via Delta Sharing)."""
    return {"materials": SAP_MATERIALS, "count": len(SAP_MATERIALS)}


@router.get("/sap/services")
async def get_sap_services():
    """SAP service contracts (via Delta Sharing)."""
    return {"services": SAP_SERVICES, "count": len(SAP_SERVICES)}


@router.get("/sap/equipment")
async def get_sap_equipment():
    """SAP equipment inventory (via Delta Sharing)."""
    return {"equipment": SAP_EQUIPMENT, "count": len(SAP_EQUIPMENT)}

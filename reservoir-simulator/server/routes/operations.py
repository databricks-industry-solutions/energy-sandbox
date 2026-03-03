import json
from fastapi import APIRouter
from .simulate import _well_timeseries, _operations_cache
from ..db import db

router = APIRouter()


@router.get("/operations/{run_id}")
async def get_operations(run_id: str):
    """Return derived well-level operational activities for a completed run."""
    ops = _operations_cache.get(run_id)
    if ops is not None:
        return {"run_id": run_id, "operations": ops, "count": len(ops)}

    # Try DB fallback
    row = await db.fetchrow(
        "SELECT operations FROM run_operations WHERE run_id=?", run_id,
    )
    if row and row.get("operations"):
        ops = json.loads(row["operations"])
        _operations_cache[run_id] = ops
        return {"run_id": run_id, "operations": ops, "count": len(ops)}

    return {"run_id": run_id, "operations": [], "count": 0,
            "message": "No operations data. Run a simulation first."}


@router.get("/operations/{run_id}/summary")
async def operations_summary(run_id: str):
    """Per-well and per-category activity summary."""
    ops = _operations_cache.get(run_id, [])
    if not ops:
        row = await db.fetchrow(
            "SELECT operations FROM run_operations WHERE run_id=?", run_id,
        )
        if row and row.get("operations"):
            ops = json.loads(row["operations"])

    if not ops:
        return {"run_id": run_id, "by_well": {}, "by_category": {}}

    by_well: dict = {}
    by_category: dict = {}
    for op in ops:
        wn = op["well_name"]
        cat = op["category"]
        by_well.setdefault(wn, []).append(op["activity_type"])
        by_category.setdefault(cat, {"count": 0, "total_days": 0})
        by_category[cat]["count"] += 1
        by_category[cat]["total_days"] += op["duration_days"]

    return {"run_id": run_id, "by_well": by_well, "by_category": by_category}

import json
from fastapi import APIRouter
from ..db import db

router = APIRouter()


@router.get("/recipes")
async def list_recipes():
    rows = await db.fetch(
        "SELECT recipe_id, name, description, version, category, steps, is_active, created_ts "
        "FROM las.processing_recipes WHERE is_active=TRUE ORDER BY category, name"
    )
    return [_fmt(r) for r in rows]


@router.get("/recipes/{recipe_id}")
async def get_recipe(recipe_id: str):
    r = await db.fetchrow(
        "SELECT recipe_id, name, description, version, category, steps, is_active, created_ts "
        "FROM las.processing_recipes WHERE recipe_id=$1", recipe_id
    )
    if not r:
        return {"error": "not found"}
    runs = await db.fetch(
        "SELECT run_id, well_id, status, started_ts, completed_ts, metrics "
        "FROM las.processing_runs WHERE recipe_id=$1 ORDER BY started_ts DESC LIMIT 10", recipe_id
    )
    return {**_fmt(r), "recent_runs": [_fmt_run(x) for x in runs]}


@router.get("/recipes/runs/all")
async def all_runs():
    rows = await db.fetch(
        "SELECT r.run_id, r.well_id, r.recipe_id, r.status, r.started_ts, r.completed_ts, "
        "r.metrics, r.created_by, p.name as recipe_name, w.well_name "
        "FROM las.processing_runs r "
        "LEFT JOIN las.processing_recipes p ON p.recipe_id = r.recipe_id "
        "LEFT JOIN las.wells w ON w.well_id = r.well_id "
        "ORDER BY r.started_ts DESC NULLS LAST LIMIT 20"
    )
    return [_fmt_run(r) for r in rows]


def _fmt(r: dict) -> dict:
    return {
        "recipe_id":   r["recipe_id"],
        "name":        r["name"],
        "description": r["description"],
        "version":     r["version"],
        "category":    r["category"],
        "steps":       json.loads(r["steps"]) if r.get("steps") else [],
        "is_active":   r["is_active"],
        "created_ts":  r["created_ts"].isoformat() if r.get("created_ts") else None,
    }


def _fmt_run(r: dict) -> dict:
    return {
        "run_id":       r["run_id"],
        "well_id":      r.get("well_id"),
        "well_name":    r.get("well_name"),
        "recipe_id":    r.get("recipe_id"),
        "recipe_name":  r.get("recipe_name"),
        "status":       r["status"],
        "started_ts":   r["started_ts"].isoformat() if r.get("started_ts") else None,
        "completed_ts": r["completed_ts"].isoformat() if r.get("completed_ts") else None,
        "metrics":      json.loads(r["metrics"]) if r.get("metrics") else {},
        "created_by":   r.get("created_by"),
    }

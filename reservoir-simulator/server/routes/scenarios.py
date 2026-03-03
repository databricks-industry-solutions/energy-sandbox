import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from ..db import db

router = APIRouter()


class ScenarioCreate(BaseModel):
    name: str
    deck_id: str
    description: Optional[str] = ""
    config: Optional[dict] = {}


@router.get("/scenarios")
async def list_scenarios():
    rows = await db.fetch(
        "SELECT id, name, deck_id, description, config, created_at "
        "FROM scenarios ORDER BY created_at DESC"
    )
    for r in rows:
        if isinstance(r.get("config"), str):
            r["config"] = json.loads(r["config"])
    return rows


@router.post("/scenarios")
async def create_scenario(req: ScenarioCreate):
    row_id = await db.execute(
        "INSERT INTO scenarios (name, deck_id, description, config) VALUES (?,?,?,?)",
        req.name, req.deck_id, req.description or "", json.dumps(req.config or {}),
    )
    row = await db.fetchrow(
        "SELECT id, name, deck_id, description, config, created_at FROM scenarios WHERE id=?",
        row_id,
    )
    if row and isinstance(row.get("config"), str):
        row["config"] = json.loads(row["config"])
    return row or {"error": "Failed to create scenario"}


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: int):
    row = await db.fetchrow(
        "SELECT id, name, deck_id, description, config, created_at FROM scenarios WHERE id=?",
        scenario_id,
    )
    if row and isinstance(row.get("config"), str):
        row["config"] = json.loads(row["config"])
    return row or {"error": "Not found"}


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: int):
    await db.execute("DELETE FROM scenarios WHERE id=?", scenario_id)
    return {"deleted": scenario_id}

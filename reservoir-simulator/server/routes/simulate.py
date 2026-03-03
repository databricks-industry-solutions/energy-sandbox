import asyncio
import json
import random
import uuid
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
from ..db import db
from ..simulator import (
    _init_grid, _advance_timestep, compute_well_production,
    compute_field_summary, TOTAL_TIMESTEPS, DAYS_PER_STEP, NI, NJ, NK
)
from ..operations import derive_operations
from ..costs import estimate_full_cycle_costs, compute_lifting_costs
from ..delta_sharing import sync_outbound

router = APIRouter()

# WebSocket connections per run_id
_ws_connections: Dict[str, Set[WebSocket]] = {}

# In-memory store for grid snapshots (run_id -> timestep -> cells)
_grid_snapshots: Dict[str, Dict[int, list]] = {}

# In-memory store for well time series (run_id -> list of per-timestep results)
_well_timeseries: Dict[str, list] = {}

# In-memory store for field summaries (run_id -> list of per-timestep summaries)
_field_summaries: Dict[str, list] = {}

# V2 caches — operations and cost data per run
_operations_cache: Dict[str, list] = {}
_costs_cache: Dict[str, dict] = {}
_delta_sharing_cache: Dict[str, dict] = {}


class SimulateRequest(BaseModel):
    scenario_id: int
    run_name: Optional[str] = None


@router.post("/simulate")
async def start_simulation(req: SimulateRequest):
    run_id = str(uuid.uuid4())[:12]

    # Get scenario config
    scenario = await db.fetchrow(
        "SELECT id, name, deck_id, config FROM scenarios WHERE id=?",
        req.scenario_id,
    )
    if not scenario:
        return {"error": "Scenario not found"}

    config = scenario.get("config", {})
    if isinstance(config, str):
        config = json.loads(config)

    # Create run record
    await db.execute(
        "INSERT INTO simulation_runs (id, scenario_id, status, total_timesteps, created_at) "
        "VALUES (?, ?, 'PENDING', ?, datetime('now'))",
        run_id, req.scenario_id, TOTAL_TIMESTEPS,
    )

    # Start background simulation task
    asyncio.create_task(_run_simulation(run_id, req.scenario_id, config))

    return {"run_id": run_id, "status": "PENDING", "total_timesteps": TOTAL_TIMESTEPS}


async def _run_simulation(run_id: str, scenario_id: int, config: dict):
    """Background task: runs simulation and streams updates via WebSocket."""
    rng = random.Random(hash(run_id))

    wells_config = config.get("wells", [
        {"name": "B-2H", "type": "PROD", "i": 5,  "j": 7},
        {"name": "D-1H", "type": "PROD", "i": 9,  "j": 4},
        {"name": "E-3H", "type": "PROD", "i": 5,  "j": 3},
        {"name": "D-2H", "type": "PROD", "i": 15, "j": 3},
    ])

    await db.execute(
        "UPDATE simulation_runs SET status='RUNNING', started_at=datetime('now') WHERE id=?",
        run_id,
    )
    await _broadcast(run_id, {"type": "status", "data": {"status": "RUNNING", "run_id": run_id}})

    cells = _init_grid()
    _grid_snapshots[run_id] = {}
    _well_timeseries[run_id] = []
    _field_summaries[run_id] = []

    _grid_snapshots[run_id][0] = [dict(c) for c in cells]

    cum_oil   = {w["name"]: 0.0 for w in wells_config if w.get("type") != "INJ"}
    cum_gas   = {w["name"]: 0.0 for w in wells_config if w.get("type") != "INJ"}
    cum_water = {w["name"]: 0.0 for w in wells_config if w.get("type") != "INJ"}

    try:
        for ts in range(1, TOTAL_TIMESTEPS + 1):
            changed_cells = _advance_timestep(cells, ts, rng, wells_config)

            well_results = compute_well_production(ts, rng, cells, wells_config)
            for wr in well_results:
                wn = wr["well_name"]
                cum_oil[wn]   = cum_oil.get(wn, 0)   + wr["oil_rate_stbd"]   * DAYS_PER_STEP
                cum_gas[wn]   = cum_gas.get(wn, 0)   + wr["gas_rate_mscfd"]  * DAYS_PER_STEP
                cum_water[wn] = cum_water.get(wn, 0) + wr["water_rate_stbd"] * DAYS_PER_STEP
                wr["cum_oil_stb"]   = round(cum_oil[wn], 0)
                wr["cum_gas_mscf"]  = round(cum_gas[wn], 0)
                wr["cum_water_stb"] = round(cum_water[wn], 0)

            field_summary = compute_field_summary(well_results)
            field_summary["timestep"]      = ts
            field_summary["day"]           = round(ts * DAYS_PER_STEP, 1)
            field_summary["cum_oil_stb"]   = round(sum(cum_oil.values()), 0)
            field_summary["cum_gas_mscf"]  = round(sum(cum_gas.values()), 0)
            field_summary["cum_water_stb"] = round(sum(cum_water.values()), 0)

            _grid_snapshots[run_id][ts] = [dict(c) for c in cells]
            _well_timeseries[run_id].append(well_results)
            _field_summaries[run_id].append(field_summary)

            progress = int(ts / TOTAL_TIMESTEPS * 100)

            await db.execute(
                "UPDATE simulation_runs SET progress=?, current_timestep=? WHERE id=?",
                progress, float(ts), run_id,
            )

            await _broadcast(run_id, {
                "type":     "grid_update",
                "timestep": ts,
                "progress": progress,
                "cells":    changed_cells,   # send ALL changed cells, no cap
                "field":    field_summary,
            })
            await _broadcast(run_id, {
                "type": "progress",
                "data": {"timestep": ts, "progress": progress, "total": TOTAL_TIMESTEPS},
            })

            await asyncio.sleep(0.12)   # ~8 timesteps/sec for fluid animation

        await db.execute(
            "UPDATE simulation_runs SET status='SUCCEEDED', progress=100, finished_at=datetime('now') WHERE id=?",
            run_id,
        )

        # ── V2: Post-simulation — derive operations, costs, sync to SAP ──
        try:
            ops = derive_operations(_well_timeseries[run_id], wells_config)
            _operations_cache[run_id] = ops
            await db.execute(
                "INSERT INTO run_operations (run_id, operations) VALUES (?,?)",
                run_id, json.dumps(ops),
            )

            costs = estimate_full_cycle_costs(ops)
            _costs_cache[run_id] = costs
            # Store without costed_operations (too large) — keep summary
            costs_summary = {k: v for k, v in costs.items() if k != "costed_operations"}
            costs_summary["costed_operations_count"] = len(costs.get("costed_operations", []))
            await db.execute(
                "INSERT INTO run_costs (run_id, costs) VALUES (?,?)",
                run_id, json.dumps(costs_summary),
            )

            ds = sync_outbound(run_id, ops, costs, _well_timeseries[run_id])
            _delta_sharing_cache[run_id] = ds
            await db.execute(
                "INSERT INTO delta_sharing_log (run_id, direction, sync_data) VALUES (?,?,?)",
                run_id, "OUTBOUND", json.dumps(ds),
            )
            print(f"V2 post-sim: {len(ops)} operations, ${costs['total_cost_usd']:,.0f} total cost, Delta Sharing synced")
        except Exception as e:
            print(f"V2 post-sim warning: {e}")

        await _broadcast(run_id, {
            "type": "complete",
            "data": {"run_id": run_id, "status": "SUCCEEDED", "total_timesteps": TOTAL_TIMESTEPS},
        })

    except Exception as e:
        print(f"Simulation error for {run_id}: {e}")
        await db.execute(
            "UPDATE simulation_runs SET status='FAILED', log_tail=?, finished_at=datetime('now') WHERE id=?",
            str(e)[:500], run_id,
        )
        await _broadcast(run_id, {
            "type": "error",
            "data": {"run_id": run_id, "error": str(e)},
        })


async def _broadcast(run_id: str, message: dict):
    connections = _ws_connections.get(run_id, set())
    dead = set()
    data = json.dumps(message)
    for ws in connections:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    for ws in dead:
        connections.discard(ws)


@router.websocket("/ws/simulate/{run_id}")
async def websocket_simulate(websocket: WebSocket, run_id: str):
    await websocket.accept()
    if run_id not in _ws_connections:
        _ws_connections[run_id] = set()
    _ws_connections[run_id].add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        _ws_connections.get(run_id, set()).discard(websocket)
    except Exception:
        _ws_connections.get(run_id, set()).discard(websocket)


@router.get("/runs")
async def list_runs():
    rows = await db.fetch(
        "SELECT r.id, r.scenario_id, r.status, r.progress, r.current_timestep, "
        "r.total_timesteps, r.started_at, r.finished_at, r.created_at, "
        "s.name as scenario_name, s.deck_id "
        "FROM simulation_runs r "
        "LEFT JOIN scenarios s ON r.scenario_id = s.id "
        "ORDER BY r.created_at DESC LIMIT 20"
    )
    return rows


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    row = await db.fetchrow(
        "SELECT r.id, r.scenario_id, r.status, r.progress, r.current_timestep, "
        "r.total_timesteps, r.log_tail, r.started_at, r.finished_at, r.created_at, "
        "s.name as scenario_name, s.deck_id "
        "FROM simulation_runs r "
        "LEFT JOIN scenarios s ON r.scenario_id = s.id "
        "WHERE r.id=?", run_id,
    )
    return row or {"error": "Run not found"}


@router.get("/runs/{run_id}/grid/{timestep}")
async def get_grid_snapshot(run_id: str, timestep: int):
    snapshots = _grid_snapshots.get(run_id, {})
    if timestep in snapshots:
        return {"run_id": run_id, "timestep": timestep, "cells": snapshots[timestep]}
    return {"error": f"No snapshot for run {run_id} timestep {timestep}"}


@router.get("/runs/{run_id}/wells")
async def get_run_wells(run_id: str):
    series = _well_timeseries.get(run_id, [])
    if not series:
        return {"run_id": run_id, "wells": [], "timesteps": []}

    well_names = sorted(set(w["well_name"] for ts_data in series for w in ts_data))
    wells_data = {wn: [] for wn in well_names}
    for ts_data in series:
        for w in ts_data:
            wells_data[w["well_name"]].append(w)

    return {"run_id": run_id, "wells": wells_data, "well_names": well_names}

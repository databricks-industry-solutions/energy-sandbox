"""
Subsea Drone Autopilot – FastAPI Backend
Serves React static files + API endpoints for Autopilot and Inspection agents.
"""

import json
import asyncio
import random
import time
import math
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from agents.subsea_autopilot_agent import (
    run_agent as autopilot_sync,
    run_agent_stream as autopilot_stream,
)
from agents.subsea_inspection_agent import (
    run_agent_stream as inspection_stream,
)
from agents.maintenance_advisor_agent import (
    run_agent_stream as maintenance_stream,
)
from agents.knowledge_agent import (
    run_agent_stream as knowledge_stream,
)
import db
from simulator import get_simulator

app = FastAPI(title="Subsea Drone Autopilot", version="1.0.0")

# ── Request / Response Models ───────────────────────────────

class MissionRequest(BaseModel):
    asset_id: str
    asset_type: str
    target_depth_m: float | None = None
    inspection_type: str = "visual"
    risk_level: str = "medium"
    notes: str = ""

class InspectionRequest(BaseModel):
    mission_id: str


# ── Helper: build natural-language prompt from request ──────

def _build_autopilot_prompt(req: MissionRequest) -> str:
    parts = [
        f"Plan and launch an inspection mission for asset '{req.asset_id}' "
        f"(type: {req.asset_type}).",
        f"Inspection type: {req.inspection_type}.",
        f"Risk level: {req.risk_level}.",
    ]
    if req.target_depth_m is not None:
        parts.append(f"Target depth: {req.target_depth_m} m.")
    if req.notes:
        parts.append(f"Operator notes: {req.notes}")
    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════
# 1. Sync Mission Planner
# ═══════════════════════════════════════════════════════════════

@app.post("/api/autopilot/plan-and-launch")
async def plan_and_launch(req: MissionRequest):
    """Synchronous autopilot – returns full mission JSON."""
    prompt = _build_autopilot_prompt(req)
    result = await asyncio.to_thread(autopilot_sync, prompt)
    return JSONResponse(content=result)


# ═══════════════════════════════════════════════════════════════
# 2. Streaming Mission Planner (SSE)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/autopilot/plan-and-launch/stream")
async def plan_and_launch_stream(req: MissionRequest):
    """Streaming autopilot via Server-Sent Events."""
    prompt = _build_autopilot_prompt(req)

    async def event_generator() -> AsyncGenerator[dict, None]:
        for evt in autopilot_stream(prompt):
            yield {
                "event": evt["event"],
                "data": json.dumps(evt["data"]),
            }

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════════
# 3. Streaming Inspection Report (SSE)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/inspection/report/stream")
async def inspection_report_stream(req: InspectionRequest):
    """Streaming inspection analysis via Server-Sent Events."""
    prompt = (
        f"Analyze inspection mission '{req.mission_id}'. "
        "Retrieve frames, run inference, check telemetry, query manuals, "
        "and produce the structured inspection report."
    )

    async def event_generator() -> AsyncGenerator[dict, None]:
        for evt in inspection_stream(prompt):
            yield {
                "event": evt["event"],
                "data": json.dumps(evt["data"]),
            }

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════════
# 4. Data endpoints (for UI)
# ═══════════════════════════════════════════════════════════════

@app.get("/api/drones")
async def list_drones():
    """List all drone statuses for the fleet overview."""
    drones = await asyncio.to_thread(db.get_all_drones)
    return JSONResponse(content=drones)

@app.get("/api/inspections/{mission_id}")
async def get_inspection(mission_id: str):
    """Get inspection record."""
    record = await asyncio.to_thread(db.get_inspection, mission_id)
    if not record:
        return JSONResponse(content={"error": "Not found"}, status_code=404)
    return JSONResponse(content=record)


@app.get("/api/debug/db")
async def debug_db():
    """Debug endpoint to test DB connectivity."""
    import traceback
    results = {}
    try:
        drones = await asyncio.to_thread(db.sql_query, "SELECT drone_id, state FROM oil_pump_monitor_catalog.subsea.drone_status LIMIT 3")
        results["drones"] = drones
    except Exception as e:
        results["drones_error"] = f"{e}\n{traceback.format_exc()}"
    try:
        missions = await asyncio.to_thread(db.sql_query, "SELECT mission_id, status FROM inspections LIMIT 3")
        results["missions"] = missions
    except Exception as e:
        results["missions_error"] = f"{e}\n{traceback.format_exc()}"
    try:
        alerts = await asyncio.to_thread(db.sql_query, "SELECT alert_id, severity FROM alerts LIMIT 3")
        results["alerts"] = alerts
    except Exception as e:
        results["alerts_error"] = f"{e}\n{traceback.format_exc()}"
    results["warehouse_id"] = db.WAREHOUSE_ID
    results["catalog"] = db.CATALOG
    results["schema"] = db.SCHEMA
    return JSONResponse(content=results)


# ═══════════════════════════════════════════════════════════════
# 5. Live Inspection Viewer – frames + streaming analysis
# ═══════════════════════════════════════════════════════════════

# Simulated defect types with realistic subsea characteristics
# Each type maps to real generated frame images in /frames/
_DEFECT_CATALOG = [
    {"type": "corrosion", "parts": ["riser_clamp_A3", "manifold_flange_B2", "flowline_joint_7", "hull_plate_P12"],
     "color": "#ef4444", "severity_range": (0.3, 0.95),
     "frame_images": ["FRM-C001", "FRM-C002", "FRM-C003", "FRM-C004", "FRM-C005", "FRM-X001"]},
    {"type": "coating_damage", "parts": ["riser_section_4", "hull_weld_W8", "mooring_chain_link_22"],
     "color": "#f97316", "severity_range": (0.2, 0.7),
     "frame_images": ["FRM-D001", "FRM-D002"]},
    {"type": "marine_growth", "parts": ["riser_base", "manifold_valve_V3", "anode_sled_2"],
     "color": "#22c55e", "severity_range": (0.1, 0.5),
     "frame_images": ["FRM-M001", "FRM-M002", "FRM-M003", "FRM-X003"]},
    {"type": "anode_depletion", "parts": ["anode_A1", "anode_A4", "anode_B2"],
     "color": "#eab308", "severity_range": (0.4, 0.85),
     "frame_images": ["FRM-A001", "FRM-A002", "FRM-X004"]},
    {"type": "crack", "parts": ["weld_toe_J5", "brace_connection_C1", "riser_clamp_A3"],
     "color": "#dc2626", "severity_range": (0.6, 0.98),
     "frame_images": ["FRM-K001", "FRM-K002", "FRM-K003", "FRM-X002"]},
    {"type": "no_issue", "parts": ["section_clean"], "color": "#06b6d4", "severity_range": (0.0, 0.05),
     "frame_images": ["FRM-N001", "FRM-N002", "FRM-N003", "FRM-N004", "FRM-N005"]},
]


def _generate_demo_frames(mission_id: str, count: int = 24) -> list[dict]:
    """Generate realistic simulated inspection frames for demo."""
    rng = random.Random(hash(mission_id))
    frames = []
    base_depth = rng.uniform(60, 200)

    for i in range(count):
        # Most frames are clean, some have defects (realistic distribution)
        if rng.random() < 0.35:
            defect = rng.choice(_DEFECT_CATALOG[:-1])  # skip no_issue
            severity = round(rng.uniform(*defect["severity_range"]), 3)
            defect_type = defect["type"]
            asset_part = rng.choice(defect["parts"])
            color = defect["color"]
            # Bounding box for the defect annotation
            bx = rng.randint(10, 50)
            by = rng.randint(10, 50)
            bw = rng.randint(15, 40)
            bh = rng.randint(15, 40)
            real_frame = rng.choice(defect["frame_images"])
            model_output = {
                "defect_type": defect_type,
                "confidence": round(rng.uniform(0.55, 0.98), 2),
                "bbox": {"x": bx, "y": by, "w": bw, "h": bh},
                "color": color,
            }
        else:
            severity = round(rng.uniform(0.0, 0.05), 3)
            defect_type = "no_issue"
            asset_part = "section_clean"
            real_frame = rng.choice(_DEFECT_CATALOG[-1]["frame_images"])
            model_output = {"defect_type": "no_issue", "confidence": 0.99, "bbox": None, "color": "#06b6d4"}

        depth = round(base_depth + math.sin(i * 0.3) * 15 + rng.uniform(-3, 3), 1)
        frames.append({
            "frame_id": f"FRM-{mission_id[-8:]}-{i:03d}",
            "index": i,
            "ts": f"2026-03-14T{10 + i // 60:02d}:{i % 60:02d}:00Z",
            "depth_m": depth,
            "image_path": f"/frames/{real_frame}.jpg",
            "severity_score": severity,
            "defect_type": defect_type,
            "asset_part": asset_part,
            "model_output": model_output,
            "camera_pose": {
                "roll": round(rng.uniform(-5, 5), 1),
                "pitch": round(rng.uniform(-10, 10), 1),
                "yaw": round(rng.uniform(0, 360), 1),
            },
            # Visual parameters for the synthetic underwater image
            "visual": {
                "visibility_m": round(rng.uniform(3, 15), 1),
                "water_color": rng.choice(["#0a3d5c", "#0c4a6e", "#0e2f44", "#083344", "#0b3954"]),
                "particulate": round(rng.uniform(0.1, 0.8), 2),
                "light_angle": rng.randint(20, 160),
            },
        })

    return sorted(frames, key=lambda f: f["ts"])


@app.get("/api/inspection/{mission_id}/frames")
async def get_inspection_frames(mission_id: str):
    """Get all frames for a mission (from DB or demo-generated)."""
    # Try real DB first
    real_frames = await asyncio.to_thread(db.get_inspection_frames, mission_id, 200)
    if real_frames:
        return JSONResponse(content=real_frames)
    # Fall back to demo frames
    return JSONResponse(content=_generate_demo_frames(mission_id))


@app.post("/api/inspection/{mission_id}/analyze-frame")
async def analyze_single_frame(mission_id: str, request: Request):
    """Simulate real-time ML analysis of a single frame."""
    body = await request.json()
    frame_id = body.get("frame_id", "")

    # Simulate inference latency
    await asyncio.sleep(random.uniform(0.3, 1.2))

    frames = _generate_demo_frames(mission_id)
    frame = next((f for f in frames if f["frame_id"] == frame_id), None)
    if not frame:
        return JSONResponse(content={"error": "Frame not found"}, status_code=404)

    return JSONResponse(content={
        "frame_id": frame_id,
        "model_output": frame["model_output"],
        "severity_score": frame["severity_score"],
        "analysis": _build_frame_analysis(frame),
    })


def _build_frame_analysis(frame: dict) -> str:
    """Generate a human-readable analysis string for a frame."""
    mo = frame["model_output"]
    dt = mo["defect_type"]
    conf = mo["confidence"]

    if dt == "no_issue":
        return f"No defects detected. Surface condition appears normal at {frame['depth_m']}m depth. Confidence: {conf:.0%}."

    severity = frame["severity_score"]
    sev_label = "HIGH" if severity > 0.6 else "MEDIUM" if severity > 0.3 else "LOW"
    analyses = {
        "corrosion": f"Corrosion detected on {frame['asset_part']}. Estimated affected area suggests {sev_label} severity. Surface pitting and oxide deposits visible. Confidence: {conf:.0%}.",
        "coating_damage": f"Coating degradation on {frame['asset_part']}. Exposed substrate visible with {sev_label} extent. Blistering and delamination patterns consistent with cathodic disbondment. Confidence: {conf:.0%}.",
        "marine_growth": f"Marine growth accumulation on {frame['asset_part']}. {sev_label} coverage density. Species appear to include hydroids and barnacles. May obscure underlying defects. Confidence: {conf:.0%}.",
        "anode_depletion": f"Sacrificial anode {frame['asset_part']} shows significant consumption. {sev_label} depletion level — remaining protective capacity may be insufficient. Confidence: {conf:.0%}.",
        "crack": f"Linear indication detected at {frame['asset_part']}. {sev_label} severity — orientation and length suggest fatigue cracking. NDT follow-up recommended. Confidence: {conf:.0%}.",
    }
    return analyses.get(dt, f"{dt} detected at {frame['asset_part']}. Severity: {sev_label}.")


class LiveAnalysisRequest(BaseModel):
    mission_id: str
    auto_analyze: bool = True


@app.post("/api/inspection/live-analysis/stream")
async def live_analysis_stream(req: LiveAnalysisRequest):
    """Stream frame-by-frame analysis in real time — simulates the drone
    sending frames back and the ML pipeline processing each one."""

    frames = _generate_demo_frames(req.mission_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        yield {"event": "status", "data": json.dumps({
            "message": f"Mission {req.mission_id} — receiving {len(frames)} frames…",
            "total_frames": len(frames),
        })}

        defect_counts: dict[str, int] = {}
        high_severity_frames: list[str] = []

        for i, frame in enumerate(frames):
            # Simulate frame arrival interval
            await asyncio.sleep(random.uniform(0.4, 1.5))

            analysis = _build_frame_analysis(frame)
            dt = frame["model_output"]["defect_type"]
            if dt != "no_issue":
                defect_counts[dt] = defect_counts.get(dt, 0) + 1
            if frame["severity_score"] > 0.6:
                high_severity_frames.append(frame["frame_id"])

            yield {"event": "frame", "data": json.dumps({
                "frame": frame,
                "analysis": analysis,
                "progress": round((i + 1) / len(frames) * 100, 1),
                "frames_processed": i + 1,
                "total_frames": len(frames),
                "running_defect_counts": defect_counts,
                "high_severity_count": len(high_severity_frames),
            })}

        # Final summary
        yield {"event": "complete", "data": json.dumps({
            "message": "Analysis complete.",
            "total_frames": len(frames),
            "defect_counts": defect_counts,
            "high_severity_frames": high_severity_frames,
            "summary": (
                f"Processed {len(frames)} frames. "
                f"Found {sum(defect_counts.values())} defects across {len(defect_counts)} categories. "
                f"{len(high_severity_frames)} frames flagged as high severity."
            ),
        })}

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════════
# 6. Maintenance Advisor Agent (streaming)
# ═══════════════════════════════════════════════════════════════

@app.post("/api/maintenance/advise/stream")
async def maintenance_advise_stream(request: Request):
    """Streaming maintenance advisor — analyzes fleet health and recommends work."""
    body = await request.json()
    prompt = body.get("prompt", "Analyze the full fleet and provide a maintenance schedule with prioritized recommendations.")

    async def event_generator() -> AsyncGenerator[dict, None]:
        for evt in maintenance_stream(prompt):
            yield {"event": evt["event"], "data": json.dumps(evt["data"])}

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════════
# 7. Knowledge Assistant Agent (streaming)
# ═══════════════════════════════════════════════════════════════

class KnowledgeRequest(BaseModel):
    question: str

@app.post("/api/knowledge/ask/stream")
async def knowledge_ask_stream(req: KnowledgeRequest):
    """Streaming knowledge assistant — answers operator questions via RAG."""
    async def event_generator() -> AsyncGenerator[dict, None]:
        for evt in knowledge_stream(req.question):
            yield {"event": evt["event"], "data": json.dumps(evt["data"])}

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════════
# 8. Simulator-powered endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/api/sim/fleet")
async def sim_fleet():
    """Get full fleet summary from simulator (advances one tick)."""
    sim = get_simulator()
    return JSONResponse(content=sim.get_fleet_summary())

@app.get("/api/sim/drone/{drone_id}")
async def sim_drone(drone_id: str):
    """Get detailed drone telemetry + profile from simulator."""
    sim = get_simulator()
    return JSONResponse(content=sim.get_drone_profile(drone_id))

@app.get("/api/sim/environment")
async def sim_environment():
    """Get current environment conditions."""
    sim = get_simulator()
    from dataclasses import asdict
    return JSONResponse(content=asdict(sim.env))

@app.get("/api/assets")
async def list_assets():
    """List all subsea assets."""
    assets = await asyncio.to_thread(
        db.sql_query, "SELECT * FROM assets ORDER BY asset_type, asset_id"
    )
    return JSONResponse(content=assets)

@app.get("/api/alerts")
async def list_alerts():
    """List active alerts from Lakebase (low latency)."""
    try:
        alerts = await asyncio.to_thread(db.pg_get_alerts, False, 20)
        # Convert datetime objects to strings for JSON
        for a in alerts:
            for k, v in a.items():
                if hasattr(v, 'isoformat'):
                    a[k] = v.isoformat()
        return JSONResponse(content=alerts)
    except Exception:
        # Fallback to Delta
        alerts = await asyncio.to_thread(
            db.sql_query,
            "SELECT * FROM alerts WHERE acknowledged = false ORDER BY ts DESC LIMIT 20"
        )
        return JSONResponse(content=alerts)

@app.get("/api/alerts/all")
async def list_all_alerts():
    """List all alerts from Lakebase."""
    try:
        alerts = await asyncio.to_thread(db.pg_query, "SELECT * FROM operational_alerts ORDER BY created_at DESC LIMIT 50")
        for a in alerts:
            for k, v in a.items():
                if hasattr(v, 'isoformat'):
                    a[k] = v.isoformat()
        return JSONResponse(content=alerts)
    except Exception:
        alerts = await asyncio.to_thread(
            db.sql_query, "SELECT * FROM alerts ORDER BY ts DESC LIMIT 50"
        )
        return JSONResponse(content=alerts)

@app.get("/api/missions/recent")
async def recent_missions():
    """List recent missions with details."""
    missions = await asyncio.to_thread(
        db.sql_query,
        "SELECT * FROM inspections ORDER BY start_ts DESC LIMIT 20"
    )
    return JSONResponse(content=missions)


# ═══════════════════════════════════════════════════════════════
# Static files (React build output)
# ═══════════════════════════════════════════════════════════════

app.mount("/frames", StaticFiles(directory="static/frames"), name="frames")
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve React SPA for all non-API routes."""
    return FileResponse("static/index.html")

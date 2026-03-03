import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import db

router = APIRouter()

_SYSTEM = """You are the LAS Viewer AI — a senior petrophysicist and well-log analyst with expertise in:
- LAS (Log ASCII Standard) file formats and industry standards
- Petrophysical analysis: porosity, water saturation, lithology
- Environmental corrections: borehole size, mud type, invasion
- Curve QC: despiking, gap filling, environmental corrections
- Formation evaluation: GR, resistivity, density-neutron, sonic interpretation
- MLOps for well-log ML models (gap filling, synthetic sonic, facies prediction)
- Unity Catalog governance and Delta Lake for well log data management

Answer precisely and concisely. Use actual numbers from the context provided.
Format responses with clear sections. Reference specific depths and curve values when available.
If a correction or processing step is warranted, explain the petrophysical reason."""


class ChatReq(BaseModel):
    question: str
    well_id: str = "BAKER-001"
    history: list = []


@router.post("/advisor/chat")
async def advisor_chat(req: ChatReq):
    context = await _gather_context(req.well_id)

    messages = []
    for m in (req.history or [])[-4:]:
        if m.get("role") in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})

    user_content = f"Well context:\n{context}\n\nPetrophysicist question: {req.question}"
    messages.append({"role": "user", "content": user_content})

    def _call():
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        resp = w.serving_endpoints.query(
            name="databricks-claude-sonnet-4-5",
            messages=messages,
            system=_SYSTEM,
            max_tokens=800,
            temperature=0.2,
        )
        return resp.choices[0].message.content

    try:
        answer = await asyncio.to_thread(_call)
        return {"status": "ok", "answer": answer, "well_id": req.well_id}
    except Exception as e:
        print(f"LLM error: {e}")
        return {
            "status": "fallback",
            "answer": _fallback(req.question, req.well_id),
            "well_id": req.well_id,
        }


@router.get("/advisor/quick/{well_id}")
async def advisor_quick(well_id: str):
    """Real-time status panel — no LLM call."""
    well = await db.fetchrow(
        "SELECT well_name, status, quality_score, total_depth_ft FROM las.wells WHERE well_id=$1", well_id
    )
    cq = await db.fetch(
        "SELECT curve_name, quality_score, spike_count, gap_count "
        "FROM las.curve_quality WHERE well_id=$1 ORDER BY quality_score", well_id
    )
    anomalies = await db.fetch(
        "SELECT severity, description, curve_name, depth_start FROM las.anomalies WHERE well_id=$1", well_id
    )
    # Latest depth sample
    latest = await db.fetchrow(
        "SELECT md, gr_raw, gr_c, rhob_raw, nphi_raw, rt_raw, phi_eff, sw "
        "FROM las.depth_logs WHERE well_id=$1 ORDER BY md DESC LIMIT 1", well_id
    )
    alerts = []
    for a in anomalies:
        alerts.append({"level": a["severity"], "msg": a["description"][:80]})

    return {
        "well_id":       well_id,
        "well_name":     well["well_name"] if well else well_id,
        "status":        well["status"]    if well else "unknown",
        "quality_score": well["quality_score"] if well else 0,
        "total_depth_ft":well["total_depth_ft"] if well else 0,
        "current_depth_ft": float(latest["md"]) if latest else 0,
        "gr_latest":     float(latest["gr_c"] or latest["gr_raw"] or 0) if latest else 0,
        "rhob_latest":   float(latest["rhob_raw"] or 0) if latest else 0,
        "nphi_latest":   float(latest["nphi_raw"] or 0) if latest else 0,
        "rt_latest":     float(latest["rt_raw"] or 0) if latest else 0,
        "phi_eff":       float(latest["phi_eff"] or 0) if latest else 0,
        "sw":            float(latest["sw"] or 0) if latest else 0,
        "curve_quality": [dict(c) for c in cq],
        "alerts":        alerts[:5],
    }


async def _gather_context(well_id: str) -> str:
    well = await db.fetchrow(
        "SELECT well_name, basin, county, state, status, quality_score, total_depth_ft, well_type, notes "
        "FROM las.wells WHERE well_id=$1", well_id
    )
    cq = await db.fetch(
        "SELECT curve_name, coverage_pct, spike_count, gap_count, quality_score "
        "FROM las.curve_quality WHERE well_id=$1 ORDER BY quality_score", well_id
    )
    formations = await db.fetch(
        "SELECT formation_name, top_md, base_md, zone_type, lithology_desc "
        "FROM las.formation_tops WHERE well_id=$1 ORDER BY top_md", well_id
    )
    anomalies = await db.fetch(
        "SELECT curve_name, depth_start, depth_end, anomaly_type, severity, description "
        "FROM las.anomalies WHERE well_id=$1 ORDER BY depth_start", well_id
    )
    # Zone stats
    zone_stats = await db.fetch(
        "SELECT ft.formation_name, ft.zone_type, "
        "ROUND(AVG(d.gr_raw)::numeric,1) as avg_gr, "
        "ROUND(AVG(d.rhob_raw)::numeric,3) as avg_rhob, "
        "ROUND(AVG(d.nphi_raw)::numeric,3) as avg_nphi, "
        "ROUND(EXP(AVG(LN(NULLIF(d.rt_raw,0))))::numeric,2) as gm_rt, "
        "ROUND(AVG(d.phi_eff)::numeric,3) as avg_phi_eff, "
        "ROUND(AVG(d.sw)::numeric,3) as avg_sw "
        "FROM las.formation_tops ft "
        "JOIN las.depth_logs d ON d.well_id=ft.well_id AND d.md BETWEEN ft.top_md AND ft.base_md "
        "WHERE ft.well_id=$1 GROUP BY ft.formation_name, ft.zone_type ORDER BY MIN(ft.top_md)", well_id
    )

    lines = []
    if well:
        lines.append(f"WELL: {well_id} — {well['well_name']} | {well['basin']}, {well['state']}")
        lines.append(f"Type: {well['well_type']} | Status: {well['status']} | Quality: {well['quality_score']}/100")
        lines.append(f"TD: {well['total_depth_ft']} ft | {well.get('notes','')}")

    if formations:
        lines.append("\nFORMATIONS (top to bottom):")
        for f in formations:
            lines.append(f"  {f['formation_name']}: {f['top_md']}-{f['base_md']} ft [{f['zone_type']}] — {f['lithology_desc']}")

    if zone_stats:
        lines.append("\nZONE LOG STATISTICS:")
        for z in zone_stats:
            phi_str = f"  φ_eff={z['avg_phi_eff']:.3f}" if z.get("avg_phi_eff") else ""
            sw_str  = f"  Sw={z['avg_sw']:.3f}"         if z.get("avg_sw")      else ""
            lines.append(f"  {z['formation_name']} [{z['zone_type']}]: GR={z['avg_gr']} API | "
                         f"RHOB={z['avg_rhob']} g/cc | NPHI={z['avg_nphi']} | RT={z['gm_rt']} Ω·m"
                         f"{phi_str}{sw_str}")

    if cq:
        lines.append("\nCURVE QC:")
        for c in cq:
            lines.append(f"  {c['curve_name']}: coverage={c['coverage_pct']:.1f}% | "
                         f"spikes={c['spike_count']} | gaps={c['gap_count']} | score={c['quality_score']}/100")

    if anomalies:
        lines.append("\nACTIVE ANOMALIES:")
        for a in anomalies:
            lines.append(f"  [{a['severity'].upper()}] {a['curve_name']} @ {a['depth_start']}-{a['depth_end']} ft: {a['description']}")

    return "\n".join(lines)


def _fallback(question: str, well_id: str) -> str:
    q = question.lower()
    if "quality" in q or "qc" in q:
        return (f"Based on the QC metrics for {well_id}, check the curve quality panel on the left. "
                "Look for coverage below 95%, spike counts > 5, or quality scores below 60 — these indicate "
                "curves requiring correction before petrophysical analysis.")
    if "porosity" in q or "phi" in q or "φ" in q:
        return ("Effective porosity (φ_eff) is computed from the density log using:\n"
                "φ_total = (ρ_matrix - ρ_bulk) / (ρ_matrix - ρ_fluid)\n"
                "  ρ_matrix = 2.65 g/cc (quartz), ρ_fluid = 1.0 g/cc\n"
                "φ_eff = φ_total × (1 - V_clay)\n"
                "In the Westwater reservoir, expect φ_eff = 0.10-0.18 in clean sand intervals.")
    if "saturation" in q or "sw" in q or "water" in q:
        return ("Water saturation uses Archie's equation: Sw = (Rw / (φ_eff² × Rt))^0.5\n"
                "Rw = 0.05 Ω·m, m = n = 2 (default cementation/saturation exponents)\n"
                "Sw < 0.5 typically indicates moveable hydrocarbons in the Westwater interval.")
    if "spike" in q or "noise" in q:
        return ("Spike detection uses a z-score filter on a 11-sample sliding window:\n"
                "A sample is flagged as a spike if |value - median| > 3.5 × MAD\n"
                "Spikes are corrected by linear interpolation between surrounding valid samples. "
                "GR spikes > 250 API and density spikes > 0.2 g/cc discontinuity are auto-flagged as CRITICAL.")
    if "sonic" in q or "dt" in q or "acoustic" in q:
        return ("For CONOCO-7H where DT is missing, the High Fidelity Reservoir recipe includes a synthetic "
                "sonic module. An XGBoost model is trained on offset wells to predict DT from "
                "GR_c, RHOB_c, NPHI_c, and RT_c. Typical RMSE ~4.5 μs/ft on validation wells.")
    return (f"I'm analysing well {well_id}. To get detailed petrophysical insights, "
            "check the QC dashboard for curve quality scores and the Log Viewer for visual inspection. "
            "The Westwater interval (8000-9200 ft) is the primary reservoir target — look for low GR (<40 API), "
            "high resistivity (>50 Ω·m), and low NPHI (<0.18) to identify hydrocarbon-bearing zones.")

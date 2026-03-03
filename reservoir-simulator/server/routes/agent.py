import asyncio
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from ..db import db
from .simulate import _field_summaries, _well_timeseries, _operations_cache, _costs_cache

router = APIRouter()

_SYSTEM = """You are the Reservoir & Operations Digital Twin Agent — a senior reservoir engineer, production operations specialist, and petroleum economist with deep expertise in:
- The Norne field (Norwegian North Sea): Fangst/Ile formation, turbidite reservoir, benchmark model
- Reservoir simulation: Res Flow analytical engine, pressure/saturation analysis
- Norne wells: B-2H, D-1H, D-2H, E-3H, B-4H (producers), C-4H (gas injector)
- Production optimization: rate control, BHP targets, artificial lift, water breakthrough
- Well operations: drilling, completions, workovers, ESP systems, chemical treatment
- Full-cycle cost estimation: D&C costs, OPEX, lifting costs per BOE, NPV, IRR
- Supply chain: SAP Business Data Cloud integration, material pricing, equipment inventory, procurement
- Delta Sharing: bidirectional data exchange between Databricks and SAP BDC, Unity Catalog governance
- Economics: NPV, IRR, DCF, sensitivity analysis, North Sea fiscal terms, scenario comparison

Answer precisely and concisely using actual numbers from the context provided.
Format responses with clear sections. Reference specific wells, timesteps, costs, and operational activities.
When discussing costs, reference SAP material IDs and vendor names where relevant.
If recommending operational changes, provide quantitative estimates of cost and production impact."""


class ChatReq(BaseModel):
    message: str
    run_id: Optional[str] = None
    scenario_id: Optional[int] = None
    history: list = []


@router.post("/agent/chat")
async def agent_chat(req: ChatReq):
    context = await _gather_context(req.run_id, req.scenario_id)

    messages = []
    for m in (req.history or [])[-6:]:
        if m.get("role") in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})

    user_content = f"Simulation context:\n{context}\n\nEngineer question: {req.message}"
    messages.append({"role": "user", "content": user_content})

    def _call():
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        resp = w.serving_endpoints.query(
            name="databricks-claude-sonnet-4-5",
            messages=messages,
            system=_SYSTEM,
            max_tokens=1000,
            temperature=0.2,
        )
        return resp.choices[0].message.content

    try:
        answer = await asyncio.to_thread(_call)
        return {"status": "ok", "answer": answer}
    except Exception as e:
        print(f"LLM error: {e}")
        return {"status": "fallback", "answer": _fallback(req.message, req.run_id)}


async def _gather_context(run_id: Optional[str], scenario_id: Optional[int]) -> str:
    lines = []

    if scenario_id:
        scenario = await db.fetchrow(
            "SELECT name, deck_id, description, config FROM scenarios WHERE id=?",
            scenario_id,
        )
        if scenario:
            config = scenario.get("config", {})
            if isinstance(config, str):
                config = json.loads(config)
            lines.append(f"SCENARIO: {scenario['name']} (deck: {scenario['deck_id']})")
            lines.append(f"Description: {scenario['description']}")
            wells = config.get("wells", [])
            lines.append(f"Wells: {len(wells)} — " + ", ".join(
                f"{w['name']}({w['type']}) at ({w['i']},{w['j']})" for w in wells
            ))
            lines.append(f"Grid: {config.get('grid', {}).get('ni', 20)}x"
                         f"{config.get('grid', {}).get('nj', 10)}x"
                         f"{config.get('grid', {}).get('nk', 5)}")
            lines.append(f"Initial pressure: {config.get('initial_pressure_bar', 500)} bar")
            lines.append(f"Porosity: {config.get('porosity', 0.08)}, "
                         f"Perm: {config.get('permeability_md', 0.05)} md")

    if run_id:
        run = await db.fetchrow(
            "SELECT id, status, progress, current_timestep, total_timesteps "
            "FROM simulation_runs WHERE id=?", run_id
        )
        if run:
            lines.append(f"\nRUN: {run_id} — Status: {run['status']} — Progress: {run['progress']}%")
            lines.append(f"Timestep: {run['current_timestep']}/{run['total_timesteps']}")

        # Get latest field summary from memory
        summaries = _field_summaries.get(run_id, [])
        if summaries:
            latest = summaries[-1]
            lines.append(f"\nLATEST FIELD RATES (day {latest['day']}):")
            lines.append(f"  Oil: {latest['field_oil_rate_stbd']} STB/d")
            lines.append(f"  Gas: {latest['field_gas_rate_mscfd']} MSCF/d")
            lines.append(f"  Water: {latest['field_water_rate_stbd']} STB/d")
            lines.append(f"  Water cut: {latest['water_cut_pct']}%")
            lines.append(f"  GOR: {latest['gor_scf_bbl']} SCF/BBL")
            lines.append(f"  Avg pressure: {latest['field_avg_pressure_bar']} bar")

            lines.append(f"\nCUMULATIVE PRODUCTION:")
            lines.append(f"  Oil: {latest.get('cum_oil_stb', 0):,.0f} STB")
            lines.append(f"  Gas: {latest.get('cum_gas_mscf', 0):,.0f} MSCF")
            lines.append(f"  Water: {latest.get('cum_water_stb', 0):,.0f} STB")

            # First vs last for decline info
            first = summaries[0]
            lines.append(f"\nDECLINE: Oil rate from {first['field_oil_rate_stbd']} to "
                         f"{latest['field_oil_rate_stbd']} STB/d over {latest['day']:.0f} days")

        # Per-well data
        series = _well_timeseries.get(run_id, [])
        if series and len(series) > 0:
            latest_wells = series[-1]
            lines.append(f"\nPER-WELL LATEST RATES:")
            for w in latest_wells:
                lines.append(
                    f"  {w['well_name']}: Oil={w['oil_rate_stbd']} STB/d, "
                    f"Water={w['water_rate_stbd']} STB/d, BHP={w['bhp_bar']} bar"
                )

        # Economics if available
        econ = await db.fetchrow(
            "SELECT npv_usd, irr, payback_year, oil_price, gas_price, discount_rate "
            "FROM economics_results WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
            run_id,
        )
        if econ:
            lines.append(f"\nECONOMICS (latest):")
            lines.append(f"  NPV: ${econ['npv_usd']:,.0f}")
            lines.append(f"  IRR: {econ['irr']*100:.1f}%")
            lines.append(f"  Payback: Year {econ['payback_year']}")
            lines.append(f"  Oil price: ${econ['oil_price']}/bbl, Gas: ${econ['gas_price']}/MSCF")

        # Operations data
        ops = _operations_cache.get(run_id, [])
        if ops:
            lines.append(f"\nOPERATIONS: {len(ops)} activities derived")
            cats = {}
            for o in ops:
                cats[o['category']] = cats.get(o['category'], 0) + 1
            for cat, count in sorted(cats.items()):
                lines.append(f"  {cat}: {count} activities")

        # Cost data
        costs = _costs_cache.get(run_id, {})
        if costs:
            lines.append(f"\nFULL-CYCLE COSTS:")
            lines.append(f"  Total: ${costs.get('total_cost_usd', 0):,.0f}")
            wc = costs.get("well_costs", {})
            for wn, data in sorted(wc.items()):
                lines.append(f"  {wn}: ${data['total']:,.0f}")

    if not lines:
        lines.append("No simulation context available. Run a simulation first.")

    return "\n".join(lines)


def _fallback(question: str, run_id: str = None) -> str:
    q = question.lower()
    if "recovery" in q or "factor" in q:
        return ("For the Norne field (Fangst/Ile formation), ultimate recovery factor is "
                "approximately 46% of OOIP — achieved through a combination of primary "
                "depletion and gas injection via C-4H. Initial oil saturation ~0.68, "
                "porosity ~0.25 (turbidite sands), with high permeability ~120 mD. "
                "Check the cumulative production in the Well Results tab.")
    if "water" in q and ("breakthrough" in q or "cut" in q):
        return ("Water breakthrough in Norne occurs progressively after ~5 years of "
                "production. B-2H and D-1H show earliest breakthrough due to their "
                "position relative to the aquifer. Monitor water saturation in the 3D "
                "view — when Sw exceeds 0.50 in well blocks, GOR and WOR increase sharply. "
                "Historical Norne water cut reached 40-60% by field end-of-life.")
    if "npv" in q or "price" in q or "economic" in q:
        return ("Norne field economics (North Sea): at $75/bbl Brent crude and 10% discount "
                "rate, project NPV is strongly positive due to high well productivity "
                "(240+ Sm³/day per well). Key value drivers: gas injection pressure maintenance "
                "extends plateau production and improves recovery. Run the Economics tab "
                "to test oil price sensitivities. North Sea OPEX is typically $8-15/boe.")
    if "pressure" in q and ("depletion" in q or "decline" in q):
        return ("Norne reservoir pressure declined from ~360 bar initial to ~300 bar by "
                "field midlife without injection. C-4H gas injection (starting year 2) "
                "provided partial pressure maintenance, slowing decline in the B and D "
                "fault segments. Switch to Pressure view in the 3D Reservoir tab to see "
                "the depletion cone expanding from each producer well.")
    if "injection" in q or "sweep" in q:
        return ("C-4H is the primary gas injector in the Norne field. Injection into the "
                "Fangst formation supports reservoir pressure and improves oil recovery "
                "by up to 8-10% of OOIP versus primary depletion alone. To model this, "
                "run the 'Norne Gas Injection' scenario and compare cumulative oil production "
                "against the base case — the pressure maintenance effect is visible in "
                "the 3D reservoir and well rate charts after ~15 timesteps.")
    if "payback" in q:
        return ("Norne field investment payback is typically 2-4 years from first oil "
                "(1997) given $8MM CAPEX per well and initial rates of 200-300 Sm³/day. "
                "At $75/bbl, all four primary producers (B-2H, D-1H, E-3H, D-2H) achieve "
                "positive NPV within 3 years. The gas injection scenario (C-4H) requires "
                "additional injection CAPEX but improves field NPV by ~15-20%.")
    return (f"I'm your Reservoir & Economics Agent for the Norne North Sea field. "
            f"I can analyze simulation results, well performance (B-2H, D-1H, E-3H, D-2H), "
            f"pressure depletion patterns, C-4H gas injection effects, and economics. "
            f"Run a simulation first using the Scenarios tab, then ask me about "
            f"recovery factors, well optimization, economics sensitivity, or "
            f"any reservoir engineering question.")

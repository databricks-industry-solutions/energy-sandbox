"""
BOP Guardian -- Rule-based agentic AI engine.
Five sub-agents (Health, Maintenance, Supply Chain, Crew, Drilling) analyse
every simulator tick and produce recommendations, crew assignments, and
respond to natural-language queries via keyword matching.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.mock_data import (
    RUL_PREDICTIONS, FAILURE_PATTERNS, SAP_WORK_ORDERS, SAP_SPARES,
    CREW, get_qualified_bop_crew, get_intervention_eta,
    get_spares_for_component, get_wo_for_equipment,
)

# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    agent: str          # HEALTH | MAINTENANCE | SUPPLY_CHAIN | CREW | DRILLING
    severity: int       # 1=INFO, 2=WARNING, 3=CRITICAL
    title: str
    detail: str
    actions: list[str]
    asset_id: str = ""
    assigned_crew: list[str] = field(default_factory=list)
    ts: str = ""

@dataclass
class CrewAssignment:
    crew_id: str
    crew_name: str
    role: str
    asset_id: str
    issue_type: str
    eta_minutes: int
    reason: str
    ts: str = ""

@dataclass
class AgentState:
    recommendations: list[Recommendation] = field(default_factory=list)
    crew_assignments: list[CrewAssignment] = field(default_factory=list)
    chat_history: list[dict] = field(default_factory=list)
    last_tick: int = 0
    _seen_anomalies: set = field(default_factory=set)

# ── Mappings ─────────────────────────────────────────────────────────────────

CERT_COMPONENT_MAP: dict[str, set[str]] = {
    "BOP_MAINT_LEVEL_II": {"ANNULAR", "UPPER_PIPE_RAM", "LOWER_PIPE_RAM", "BLIND_SHEAR_RAM"},
    "BOP_MAINT_LEVEL_III": {"ANNULAR", "UPPER_PIPE_RAM", "LOWER_PIPE_RAM", "BLIND_SHEAR_RAM", "POD_A", "POD_B"},
    "SUBSEA_SPECIALIST": {"POD_A", "POD_B", "ANNULAR"},
    "HYDRAULIC_SPECIALIST": {"PUMP", "ACCUMULATOR", "BLIND_SHEAR_RAM", "UPPER_PIPE_RAM", "LOWER_PIPE_RAM"},
    "BOP_TEST_CERTIFIED": {"ANNULAR", "UPPER_PIPE_RAM", "LOWER_PIPE_RAM", "BLIND_SHEAR_RAM"},
    "PLC_CERTIFIED": {"PLC"},
    "ELECTRICAL_HV": {"PLC", "PUMP"},
    "WELL_CONTROL_LEVEL_III": {"BLIND_SHEAR_RAM"},
    "WELL_CONTROL_LEVEL_IV": {"BLIND_SHEAR_RAM", "ANNULAR"},
}

COMPONENT_ALIASES: dict[str, list[str]] = {
    "BOP-ANN-01": ["annular", "ann", "packer", "annular preventer"],
    "BOP-UPR-01": ["upper pipe ram", "upper ram", "upr"],
    "BOP-LPR-01": ["lower pipe ram", "lower ram", "lpr"],
    "BOP-BSR-01": ["blind shear ram", "blind shear", "shear ram", "bsr"],
    "POD-A": ["pod a", "blue pod", "poda"],
    "POD-B": ["pod b", "yellow pod", "podb"],
    "PMP-01": ["pump 1", "pump1", "koomey 1", "pmp-01", "pmp01"],
    "PMP-02": ["pump 2", "pump2", "koomey 2", "pmp-02", "pmp02"],
    "ACC-01": ["accumulator", "acc", "accum"],
    "PLC-01": ["plc", "control system", "bop plc"],
}

INTENT_KEYWORDS: dict[str, list[str]] = {
    "component_health": ["health", "how is", "condition", "sensor", "reading", "status of"],
    "work_orders": ["work order", "wo ", "maintenance", "scheduled", "planned"],
    "crew": ["crew", "who", "available", "qualified", "personnel", "technician", "assign"],
    "spare_parts": ["spare", "part", "inventory", "stock", "material", "seal", "blade"],
    "rul": ["rul", "remaining useful", "failure", "predict", "risk", "fail next"],
    "summary": ["summary", "sitrep", "overall", "what's happening", "overview", "what is going on"],
    "recommendations": ["recommend", "suggest", "action", "should", "advice", "what do"],
    "drilling": ["drill", "operation", "trip", "circul", "bop test", "maintenance window"],
}

SEV_LABEL = {1: "INFO", 2: "WARNING", 3: "CRITICAL"}

# ── Agent ────────────────────────────────────────────────────────────────────

class GuardianAgent:
    MAX_RECS = 50
    MAX_ASSIGN = 30
    MAX_CHAT = 100

    def __init__(self):
        self.state = AgentState()

    # ── Per-tick analysis ────────────────────────────────────

    def analyze_tick(self, sim: dict) -> list[Recommendation]:
        self.state.last_tick = sim["tick"]
        now = datetime.now(timezone.utc).isoformat()

        # Collect from each sub-agent
        recs: list[Recommendation] = []
        recs.extend(self._health_agent(sim, now))
        recs.extend(self._maintenance_agent(sim, now))
        recs.extend(self._supply_chain_agent(sim, now))
        recs.extend(self._drilling_agent(sim, now))

        # Auto-assign crew to critical / warning recs
        assignments = self._auto_assign_crew(sim, recs, now)
        self.state.crew_assignments.extend(assignments)
        if len(self.state.crew_assignments) > self.MAX_ASSIGN:
            self.state.crew_assignments = self.state.crew_assignments[-self.MAX_ASSIGN:]

        # Attach crew names to recs
        aid_crew: dict[str, list[str]] = {}
        for a in assignments:
            aid_crew.setdefault(a.asset_id, []).append(f"{a.crew_name} ({a.eta_minutes}m)")
        for r in recs:
            if r.asset_id in aid_crew:
                r.assigned_crew = aid_crew[r.asset_id]

        # Crew-specific recs (generated after assignments)
        recs.extend(self._crew_agent(sim, assignments, now))

        self.state.recommendations.extend(recs)
        if len(self.state.recommendations) > self.MAX_RECS:
            self.state.recommendations = self.state.recommendations[-self.MAX_RECS:]

        # Prune cleared anomalies from seen set
        active = {(c["asset_id"], c.get("anomaly_type"))
                  for c in sim["components"].values() if c["anomaly_flag"]}
        self.state._seen_anomalies &= active

        return recs

    # ── Sub-agents ───────────────────────────────────────────

    def _health_agent(self, sim: dict, now: str) -> list[Recommendation]:
        recs: list[Recommendation] = []
        for c in sim["components"].values():
            if not c["anomaly_flag"]:
                continue
            key = (c["asset_id"], c.get("anomaly_type"))
            if key in self.state._seen_anomalies:
                continue
            self.state._seen_anomalies.add(key)

            hs = c["health_score"]
            sev = 3 if hs < 0.5 else 2
            atype = (c.get("anomaly_type") or "UNKNOWN").replace("_", " ")
            pattern = next((fp for fp in FAILURE_PATTERNS
                            if fp["anomaly_pattern"] == c.get("anomaly_type")), None)
            detail = f'{c["name"]} health at {hs:.0%}. Anomaly: {atype}.'
            actions = []
            if pattern:
                detail += f' Failure mode: {pattern["failure_mode"]}.'
                actions.append(pattern["fix_action"])
            if sev == 3:
                actions.insert(0, "Immediately assess component on drill floor")
            else:
                actions.append("Monitor trend and prepare for intervention")

            recs.append(Recommendation(
                agent="HEALTH", severity=sev,
                title=f"{c['asset_id']}: {atype} detected",
                detail=detail, actions=actions,
                asset_id=c["asset_id"], ts=now))
        return recs

    def _maintenance_agent(self, sim: dict, now: str) -> list[Recommendation]:
        recs: list[Recommendation] = []
        active_ids = {c["asset_id"] for c in sim["components"].values() if c["anomaly_flag"]}
        for rul in RUL_PREDICTIONS:
            aid = rul["asset_id"]
            days = rul["predicted_rul_days"]
            p7 = rul["failure_prob_7d"]

            if aid in active_ids and days < 90:
                key = (aid, "MAINT_ACCELERATED")
                if key in self.state._seen_anomalies:
                    continue
                self.state._seen_anomalies.add(key)
                wo = get_wo_for_equipment(aid)
                open_wo = [w for w in wo if w["status"] in ("OPEN", "IN_PROGRESS")]
                wo_note = (f'Active WO: {open_wo[0]["wo_id"]} ({open_wo[0]["status"]})'
                           if open_wo else "No active work order -- create one in SAP")
                recs.append(Recommendation(
                    agent="MAINTENANCE", severity=3,
                    title=f"{aid}: Accelerated degradation -- RUL {days}d",
                    detail=f"Active anomaly with RUL at {days} days. {wo_note}.",
                    actions=["Expedite maintenance", wo_note],
                    asset_id=aid, ts=now))

            elif p7 > 0.10:
                key = (aid, "MAINT_HIGH_P7")
                if key not in self.state._seen_anomalies:
                    self.state._seen_anomalies.add(key)
                    recs.append(Recommendation(
                        agent="MAINTENANCE", severity=3,
                        title=f"{aid}: High 7-day failure prob ({p7:.0%})",
                        detail=f"Near-term failure probability is {p7:.0%}. Immediate action recommended.",
                        actions=["Schedule urgent inspection", "Prepare spare parts"],
                        asset_id=aid, ts=now))

            elif days < 60:
                key = (aid, "MAINT_LOW_RUL")
                if key not in self.state._seen_anomalies:
                    self.state._seen_anomalies.add(key)
                    recs.append(Recommendation(
                        agent="MAINTENANCE", severity=2,
                        title=f"{aid}: Schedule preventive maintenance -- RUL {days}d",
                        detail=f"Remaining useful life is {days} days. Plan maintenance window.",
                        actions=["Create SAP work order", "Verify spare parts availability"],
                        asset_id=aid, ts=now))
        return recs

    def _supply_chain_agent(self, sim: dict, now: str) -> list[Recommendation]:
        recs: list[Recommendation] = []
        active_types = {c["component_type"] for c in sim["components"].values() if c["anomaly_flag"]}
        for ctype in active_types:
            spares = get_spares_for_component(ctype)
            for sp in spares:
                if sp["available_qty"] <= sp["min_stock"]:
                    key = (sp["material_id"], "LOW_STOCK_ACTIVE")
                    if key in self.state._seen_anomalies:
                        continue
                    self.state._seen_anomalies.add(key)
                    recs.append(Recommendation(
                        agent="SUPPLY_CHAIN", severity=3,
                        title=f'Low stock: {sp["description"]}',
                        detail=(f'{sp["material_id"]}: {sp["available_qty"]} available '
                                f'(min {sp["min_stock"]}). Lead time {sp["lead_time_days"]}d.'),
                        actions=[f"Emergency order from {sp['plant']}",
                                 f"Estimated cost: ${sp['unit_price']:,}"],
                        asset_id="", ts=now))
        return recs

    def _crew_agent(self, sim: dict, assignments: list[CrewAssignment], now: str) -> list[Recommendation]:
        recs: list[Recommendation] = []
        if not assignments:
            return recs
        # Check if any assignment has long ETA
        for a in assignments:
            if a.eta_minutes > 10:
                key = (a.asset_id, "CREW_LONG_ETA")
                if key in self.state._seen_anomalies:
                    continue
                self.state._seen_anomalies.add(key)
                recs.append(Recommendation(
                    agent="CREW", severity=2,
                    title=f"Long response time for {a.asset_id}: {a.eta_minutes}m",
                    detail=f"{a.crew_name} assigned but ETA is {a.eta_minutes} min from {a.role} zone.",
                    actions=["Consider waking night-shift specialist",
                             "Have driller standby at BOP panel"],
                    asset_id=a.asset_id, ts=now))
        return recs

    def _drilling_agent(self, sim: dict, now: str) -> list[Recommendation]:
        recs: list[Recommendation] = []
        op = sim["current_op"]
        has_anomaly = any(c["anomaly_flag"] for c in sim["components"].values())
        if not has_anomaly:
            return recs

        if not op["is_low_risk"]:
            key = ("RIG", "DRILL_HIGH_RISK_OP")
            if key not in self.state._seen_anomalies:
                self.state._seen_anomalies.add(key)
                recs.append(Recommendation(
                    agent="DRILLING", severity=3,
                    title=f"Active anomaly during {op['op_code']} -- assess risk",
                    detail=(f"BOP anomalies detected during {op['description']}. "
                            f"This is a non-low-risk operation."),
                    actions=["Consider pausing operation until BOP issue resolved",
                             "Notify toolpusher and OIM",
                             "Ensure backup barriers available"],
                    asset_id="", ts=now))

        # BSR anomaly during trip
        bsr = sim["components"].get("BOP-BSR-01", {})
        if bsr.get("anomaly_flag") and op["op_code"] == "TRIP":
            key = ("BOP-BSR-01", "BSR_TRIP_RISK")
            if key not in self.state._seen_anomalies:
                self.state._seen_anomalies.add(key)
                recs.append(Recommendation(
                    agent="DRILLING", severity=3,
                    title="BSR anomaly during TRIP -- well control risk",
                    detail="Blind shear ram is the primary well-control barrier during trips.",
                    actions=["Halt trip and circulate bottoms-up",
                             "Test BSR function before resuming",
                             "Notify OIM and company man"],
                    asset_id="BOP-BSR-01", ts=now))
        return recs

    # ── Auto crew assignment ─────────────────────────────────

    def _auto_assign_crew(self, sim: dict, recs: list[Recommendation],
                          now: str) -> list[CrewAssignment]:
        assignments: list[CrewAssignment] = []
        assigned_ids: set[str] = set()

        anomaly_assets = [(c["asset_id"], c["component_type"], c.get("anomaly_type", ""))
                          for c in sim["components"].values() if c["anomaly_flag"]]
        if not anomaly_assets:
            return assignments

        for aid, ctype, atype in anomaly_assets:
            # Find crew members whose certs cover this component type
            candidates = []
            for cr in CREW:
                if cr["crew_id"] in assigned_ids:
                    continue
                for cert in cr.get("certs", []):
                    if ctype in CERT_COMPONENT_MAP.get(cert, set()):
                        eta = get_intervention_eta(cr)
                        shift_bonus = 0 if cr["shift"] == "Day" else 20
                        score = eta + shift_bonus
                        candidates.append((score, eta, cr, cert))
                        break

            if not candidates:
                continue
            candidates.sort(key=lambda x: x[0])
            _, eta, best, cert = candidates[0]
            assigned_ids.add(best["crew_id"])

            assignments.append(CrewAssignment(
                crew_id=best["crew_id"], crew_name=best["name"],
                role=best["role"], asset_id=aid,
                issue_type=atype.replace("_", " "),
                eta_minutes=eta,
                reason=f'{cert.replace("_"," ")} certified, {best["zone"].replace("_"," ")} zone',
                ts=now))
        return assignments

    # ── Chat query handling ──────────────────────────────────

    def handle_query(self, query: str, sim: dict) -> str:
        q = query.lower().strip()
        intent = self._match_intent(q)
        comp = self._match_component(q)

        if intent == "summary":
            return self._fmt_summary(sim)
        if intent == "recommendations":
            return self._fmt_recs()
        if intent == "crew":
            return self._fmt_crew(comp, sim)
        if intent == "spare_parts":
            return self._fmt_parts(comp)
        if intent == "rul":
            return self._fmt_rul()
        if intent == "work_orders":
            return self._fmt_wo(comp)
        if intent == "drilling":
            return self._fmt_drilling(sim)
        if intent == "component_health" and comp:
            return self._fmt_component(comp, sim)
        if comp:
            return self._fmt_component(comp, sim)
        return self._fmt_summary(sim)

    def _match_intent(self, q: str) -> str:
        best, best_count = "unknown", 0
        for intent, kws in INTENT_KEYWORDS.items():
            count = sum(1 for kw in kws if kw in q)
            if count > best_count:
                best, best_count = intent, count
        return best

    def _match_component(self, q: str) -> str | None:
        q = q.lower()
        for aid, aliases in COMPONENT_ALIASES.items():
            if aid.lower() in q:
                return aid
            for alias in aliases:
                if alias in q:
                    return aid
        return None

    # ── Response formatters ──────────────────────────────────

    def _fmt_summary(self, sim: dict) -> str:
        status = sim["status"]
        op = sim["current_op"]
        k = sim["kpis"]
        anomalies = [c for c in sim["components"].values() if c["anomaly_flag"]]
        lines = [
            f"**SITUATION REPORT** -- Tick {sim['tick']}",
            f"",
            f"**Rig Status:** {status.replace('_',' ')} -- {sim['status_reason']}",
            f"**Current Op:** {op['description']} ({op['op_code']})",
            f"**Depth:** {k['depth_md']:,.0f} ft MD / {k['depth_tvd']:,.0f} ft TVD",
            f"**Components:** {k['healthy_components']}/{k['total_components']} healthy, "
            f"{k['active_anomalies']} anomalies",
            f"",
        ]
        if anomalies:
            lines.append("**Active Anomalies:**")
            for c in anomalies:
                lines.append(
                    f"- **{c['asset_id']}** ({c['component_type'].replace('_',' ')}): "
                    f"{(c.get('anomaly_type') or '').replace('_',' ')} -- "
                    f"health {c['health_score']:.0%}")
        else:
            lines.append("No active anomalies. All systems nominal.")

        recs = self.get_active_recommendations()
        if recs:
            lines.append("")
            lines.append(f"**Active Recommendations ({len(recs)}):**")
            for r in recs[:5]:
                sev = SEV_LABEL.get(r.severity, "INFO")
                lines.append(f"- **[{sev}]** {r.title}")

        assigns = self.state.crew_assignments[-5:]
        if assigns:
            lines.append("")
            lines.append("**Crew Assignments:**")
            for a in assigns:
                lines.append(f"- **{a.crew_name}** -> {a.asset_id} "
                             f"({a.issue_type}, ETA {a.eta_minutes}m)")
        return "\n".join(lines)

    def _fmt_component(self, aid: str, sim: dict) -> str:
        c = sim["components"].get(aid)
        if not c:
            return f"Component {aid} not found."
        hs = c["health_score"]
        lines = [
            f"**{c['name']}** ({aid})",
            f"",
            f"**Health:** {hs:.0%}",
            f"**Anomaly:** {'Yes -- ' + (c.get('anomaly_type') or '').replace('_',' ') if c['anomaly_flag'] else 'None'}",
        ]
        # RUL
        rul = next((r for r in RUL_PREDICTIONS if r["asset_id"] == aid), None)
        if rul:
            lines.append(f"**RUL:** {rul['predicted_rul_days']} days "
                         f"(7d fail prob: {rul['failure_prob_7d']:.1%}, "
                         f"30d: {rul['failure_prob_30d']:.1%})")
        # Work orders
        wos = get_wo_for_equipment(aid)
        if wos:
            lines.append(f"**Work Orders:**")
            for w in wos:
                lines.append(f"- {w['wo_id']} -- {w['description']} [{w['status']}]")
        # Spares
        spares = get_spares_for_component(c["component_type"])
        if spares:
            lines.append(f"**Spare Parts:**")
            for s in spares:
                lines.append(f"- {s['description']}: {s['available_qty']} in stock "
                             f"(min {s['min_stock']}, lead {s['lead_time_days']}d)")
        # Failure pattern
        if c["anomaly_flag"]:
            fp = next((f for f in FAILURE_PATTERNS
                       if f["anomaly_pattern"] == c.get("anomaly_type")), None)
            if fp:
                lines.append(f"")
                lines.append(f"**Failure Mode:** {fp['failure_mode']}")
                lines.append(f"**Avg Time to Failure:** {fp['avg_ttf_days']} days")
                lines.append(f"**Recommended Fix:** {fp['fix_action']}")
        # Assigned crew
        assigns = [a for a in self.state.crew_assignments if a.asset_id == aid]
        if assigns:
            lines.append(f"")
            lines.append("**Assigned Crew:**")
            for a in assigns[-3:]:
                lines.append(f"- {a.crew_name} ({a.role}) -- ETA {a.eta_minutes}m -- {a.reason}")
        return "\n".join(lines)

    def _fmt_crew(self, comp: str | None, sim: dict) -> str:
        bop_crew = get_qualified_bop_crew()
        lines = [f"**BOP-Qualified Crew** ({len(bop_crew)} on rig)", ""]
        for cr in sorted(bop_crew, key=lambda x: get_intervention_eta(x)):
            eta = get_intervention_eta(cr)
            certs = ", ".join(c.replace("_", " ") for c in cr.get("certs", []))
            lines.append(
                f"- **{cr['name']}** -- {cr['role']} | {cr['shift']} shift | "
                f"{cr['zone'].replace('_',' ')} | ETA {eta}m | {certs}")
        assigns = self.state.crew_assignments[-10:]
        if assigns:
            lines.append("")
            lines.append("**Current Assignments:**")
            for a in assigns:
                lines.append(
                    f"- **{a.crew_name}** -> {a.asset_id} ({a.issue_type}) "
                    f"ETA {a.eta_minutes}m -- {a.reason}")
        return "\n".join(lines)

    def _fmt_parts(self, comp: str | None) -> str:
        if comp:
            c_info = next((c for c in COMPONENT_ALIASES if c == comp), None)
            ctype = None
            for r in RUL_PREDICTIONS:
                if r["asset_id"] == comp:
                    ctype = r["component_type"]
                    break
            spares = get_spares_for_component(ctype) if ctype else SAP_SPARES
        else:
            spares = SAP_SPARES

        lines = [f"**Spare Parts Inventory** ({len(spares)} items)", ""]
        for s in spares:
            status = "LOW" if s["available_qty"] <= s["min_stock"] else "OK"
            lines.append(
                f"- **{s['description']}** ({s['material_id']}) -- "
                f"Qty: {s['available_qty']} (min {s['min_stock']}) [{status}] | "
                f"Lead: {s['lead_time_days']}d | ${s['unit_price']:,}")
        return "\n".join(lines)

    def _fmt_rul(self) -> str:
        sorted_rul = sorted(RUL_PREDICTIONS, key=lambda x: x["predicted_rul_days"])
        lines = ["**Remaining Useful Life Predictions** (sorted by urgency)", ""]
        for r in sorted_rul:
            days = r["predicted_rul_days"]
            risk = "CRITICAL" if days < 60 else ("WARNING" if days < 120 else "OK")
            lines.append(
                f"- **{r['asset_id']}** ({r['component_type'].replace('_',' ')}): "
                f"**{days}d** RUL [{risk}] -- "
                f"7d: {r['failure_prob_7d']:.1%}, 30d: {r['failure_prob_30d']:.1%}")
        return "\n".join(lines)

    def _fmt_wo(self, comp: str | None) -> str:
        wos = get_wo_for_equipment(comp) if comp else SAP_WORK_ORDERS
        lines = [f"**Work Orders** ({len(wos)} items)", ""]
        for w in wos:
            lines.append(
                f"- **{w['wo_id']}** [{w['status']}] P{w['priority']} -- "
                f"{w['description']} | {w['equipment_id']} | "
                f"{w['start_date']} to {w['finish_date']}")
        if not wos:
            lines.append("No work orders found.")
        return "\n".join(lines)

    def _fmt_drilling(self, sim: dict) -> str:
        op = sim["current_op"]
        lr = "LOW RISK -- maintenance window available" if op["is_low_risk"] else \
             "ACTIVE OP -- defer non-critical maintenance"
        has_anom = any(c["anomaly_flag"] for c in sim["components"].values())
        lines = [
            "**Current Drilling Operation**", "",
            f"**Operation:** {op['description']} ({op['op_code']})",
            f"**Section:** {op['section']}",
            f"**Depth:** {op['depth_md']:,.0f} ft MD / {op['depth_tvd']:,.0f} ft TVD",
            f"**Risk Level:** {lr}",
        ]
        if has_anom and not op["is_low_risk"]:
            lines.append("")
            lines.append("**WARNING:** Active BOP anomalies during non-low-risk operation. "
                         "Consider pausing until resolved.")
        elif has_anom and op["is_low_risk"]:
            lines.append("")
            lines.append("Current op is low-risk. Maintenance window available to address anomalies.")
        return "\n".join(lines)

    def _fmt_recs(self) -> str:
        recs = self.get_active_recommendations()
        if not recs:
            return "**No active recommendations.** All systems nominal."
        lines = [f"**Active Recommendations** ({len(recs)})", ""]
        for r in recs:
            sev = SEV_LABEL.get(r.severity, "INFO")
            lines.append(f"**[{sev}] {r.agent}** -- {r.title}")
            lines.append(f"  {r.detail}")
            for a in r.actions:
                lines.append(f"  - {a}")
            if r.assigned_crew:
                lines.append(f"  Crew: {', '.join(r.assigned_crew)}")
            lines.append("")
        return "\n".join(lines)

    # ── Utility ──────────────────────────────────────────────

    def get_active_recommendations(self, max_age_ticks: int = 5) -> list[Recommendation]:
        return self.state.recommendations[-15:]

    def get_critical_alerts(self) -> list[Recommendation]:
        return [r for r in self.state.recommendations[-10:] if r.severity == 3]

"""
Pipeline Command Center — Multi-Agent AI Engine
Five rule-based sub-agents for midstream pipeline monitoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from mock_data import (
    ASSETS, RUL_PREDICTIONS, FAILURE_PATTERNS, WORK_ORDERS,
    SPARE_PARTS, CREW, CERT_TO_ASSET, ZONE_ETA, NIGHT_SHIFT_PENALTY,
    CERT_TIER, INCIDENT_CREW_MATRIX, MAX_CONCURRENT_ASSIGNMENTS,
)

# ── Data Classes ───────────────────────────────────────────────────

@dataclass
class Recommendation:
    agent: str
    severity: int          # 1=INFO, 2=WARNING, 3=CRITICAL
    asset_id: str
    title: str
    detail: str
    actions: list[str]
    crew: list["CrewAssignment"] = field(default_factory=list)

    @property
    def severity_label(self) -> str:
        return {1: "INFO", 2: "WARNING", 3: "CRITICAL"}.get(self.severity, "INFO")


@dataclass
class CrewAssignment:
    crew_name: str
    asset_id: str
    issue_type: str
    eta_min: int
    cert_reason: str
    role: str = ""              # Assigned role (Lead, HSE Standby, etc.)
    skill_score: int = 0        # Skill match quality (higher = better)
    reasoning: str = ""         # AI reasoning chain for this assignment


# ── Agent State ────────────────────────────────────────────────────

class AgentState:
    def __init__(self):
        self.recommendations: list[Recommendation] = []
        self.crew_assignments: list[CrewAssignment] = []
        self.chat_history: list[dict] = []
        self.seen_anomalies: set[str] = set()

    def trim(self):
        self.recommendations = self.recommendations[-50:]
        self.crew_assignments = self.crew_assignments[-30:]
        self.chat_history = self.chat_history[-100:]


# ── Guardian Agent (orchestrator) ──────────────────────────────────

class PipelineGuardian:
    """Orchestrates 5 sub-agents per simulation tick."""

    def __init__(self):
        self.state = AgentState()

    # ── Per-Tick Analysis ──────────────────────────────────────────

    def analyze_tick(self, sim: dict):
        anomalies = sim.get("anomalies", [])
        components = {c["asset_id"]: c for c in sim.get("components", [])}
        current_op = sim.get("current_op", {})
        kpis = sim.get("kpis", {})

        new_recs: list[Recommendation] = []

        for an in anomalies[-10:]:
            key = f"{an['asset_id']}|{an['tag']}|{an['severity']}"
            if key in self.state.seen_anomalies:
                continue
            self.state.seen_anomalies.add(key)

            comp = components.get(an["asset_id"], {})
            health = comp.get("health", 1.0)
            asset_type = comp.get("type", "")

            # ── 1. PIPELINE_HEALTH_AGENT ───────────────────────────
            rec = self._health_agent(an, health, asset_type)
            if rec:
                new_recs.append(rec)

            # ── 2. INTEGRITY_AGENT ─────────────────────────────────
            rec = self._integrity_agent(an, health, asset_type)
            if rec:
                new_recs.append(rec)

            # ── 3. LEAK_DETECTION_AGENT ────────────────────────────
            rec = self._leak_agent(an, health, asset_type, sim)
            if rec:
                new_recs.append(rec)

        # ── 4. OPERATIONS_AGENT (tick-level) ───────────────────────
        ops_recs = self._operations_agent(current_op, components, kpis)
        new_recs.extend(ops_recs)

        # ── 5. COMPLIANCE_AGENT (tick-level) ───────────────────────
        comp_recs = self._compliance_agent(components, sim)
        new_recs.extend(comp_recs)

        # Auto-assign crew to new recommendations
        for rec in new_recs:
            self._auto_assign_crew(rec)

        self.state.recommendations.extend(new_recs)
        self.state.trim()

    # ── Sub-Agent: Pipeline Health ─────────────────────────────────

    def _health_agent(self, anomaly: dict, health: float, asset_type: str) -> Optional[Recommendation]:
        sev = anomaly.get("severity", "INFO")
        if sev == "INFO":
            return None

        severity = 3 if health < 0.5 else 2
        aid = anomaly["asset_id"]

        # Match failure pattern
        pattern = None
        for fp in FAILURE_PATTERNS:
            if fp["component_type"] == asset_type:
                pattern = fp
                break

        actions = [anomaly.get("message", "Monitor condition")]
        if pattern:
            actions.append(f"Root cause: {pattern['root_cause']}")
            actions.append(f"Recommended: {pattern['action']}")
            actions.append(f"Est. downtime: {pattern['downtime_hours']}h")

        return Recommendation(
            agent="HEALTH",
            severity=severity,
            asset_id=aid,
            title=f"{aid} health degraded to {health:.0%}",
            detail=anomaly.get("message", ""),
            actions=actions,
        )

    # ── Sub-Agent: Integrity Management ────────────────────────────

    def _integrity_agent(self, anomaly: dict, health: float, asset_type: str) -> Optional[Recommendation]:
        tag = anomaly.get("tag", "")
        if tag not in ("CORR_RATE", "PIPE_POT", "VIBRATION", "TEMP_BEAR"):
            return None

        aid = anomaly["asset_id"]
        rul_entry = next((r for r in RUL_PREDICTIONS if r["asset_id"] == aid), None)

        actions = []
        severity = 2
        if tag == "CORR_RATE":
            actions.append("Schedule in-line inspection (ILI) for wall-thickness verification")
            actions.append("Review CP survey records for this segment")
            if rul_entry and rul_entry["failure_prob_30d"] > 0.05:
                severity = 3
                actions.append(f"30-day failure probability {rul_entry['failure_prob_30d']:.0%} — escalate")
        elif tag == "PIPE_POT":
            severity = 3
            actions.append("Pipe-to-soil potential above -850 mV — NACE SP0169 non-compliance")
            actions.append("Increase rectifier output or deploy supplemental anodes")
        elif tag in ("VIBRATION", "TEMP_BEAR"):
            actions.append("Trend vibration & temperature — schedule predictive maintenance")
            if rul_entry:
                actions.append(f"Predicted RUL: {rul_entry['predicted_rul_days']} days ({rul_entry['model_version']})")

        return Recommendation(
            agent="INTEGRITY",
            severity=severity,
            asset_id=aid,
            title=f"Integrity concern — {aid} ({tag})",
            detail=anomaly.get("message", ""),
            actions=actions,
        )

    # ── Sub-Agent: Leak Detection ──────────────────────────────────

    def _leak_agent(self, anomaly: dict, health: float, asset_type: str, sim: dict) -> Optional[Recommendation]:
        tag = anomaly.get("tag", "")
        aid = anomaly["asset_id"]

        # Flow imbalance between meters
        if tag == "FLOW" and asset_type == "METERING":
            readings = sim.get("readings", {})
            met01_flow = readings.get("MET-01", {}).get("FLOW", 8500)
            met02_flow = readings.get("MET-02", {}).get("FLOW", 8500)
            imbalance = abs(met01_flow - met02_flow)
            if imbalance > 200:
                return Recommendation(
                    agent="LEAK_DETECT",
                    severity=3 if imbalance > 400 else 2,
                    asset_id="PIPELINE",
                    title=f"Flow imbalance {imbalance:.0f} bbl/h between inlet & delivery",
                    detail="Material balance alarm — potential leak or meter drift",
                    actions=[
                        f"Inlet: {met01_flow:.0f} bbl/h | Delivery: {met02_flow:.0f} bbl/h",
                        "Cross-check with line-pack calculations",
                        "Deploy leak survey crew if imbalance persists > 15 min",
                        "Verify meter calibration dates",
                    ],
                )

        # Pressure drop along segment
        if tag in ("PRESS_OUT", "PRESS_DN") and anomaly.get("severity") in ("WARNING", "CRITICAL"):
            return Recommendation(
                agent="LEAK_DETECT",
                severity=2,
                asset_id=aid,
                title=f"Pressure anomaly at {aid}",
                detail=anomaly.get("message", ""),
                actions=[
                    "Monitor pressure gradient across adjacent segments",
                    "Check for sudden rate-of-change (RTTM model)",
                    "Prepare aerial patrol if pressure continues declining",
                ],
            )
        return None

    # ── Sub-Agent: Operations ──────────────────────────────────────

    def _operations_agent(self, current_op: dict, components: dict, kpis: dict) -> list[Recommendation]:
        recs = []
        op = current_op.get("op", "STEADY_STATE")
        risk = current_op.get("risk", "LOW")

        if risk in ("MEDIUM", "HIGH"):
            # Check if any critical assets are degraded during risky ops
            critical = [aid for aid, c in components.items() if c.get("health", 1.0) < 0.6]
            if critical:
                recs.append(Recommendation(
                    agent="OPERATIONS",
                    severity=3,
                    asset_id=critical[0],
                    title=f"Degraded asset during {op} operation",
                    detail=f"{current_op.get('detail', '')} — {len(critical)} asset(s) below 60% health",
                    actions=[
                        f"Assets at risk: {', '.join(critical)}",
                        "Consider deferring operation until assets stabilize",
                        "Ensure isolation valves are operational",
                        "Pre-position emergency response team",
                    ],
                ))

        # Supply chain check
        for part in SPARE_PARTS:
            if part["qty"] <= part["min_qty"]:
                recs.append(Recommendation(
                    agent="OPERATIONS",
                    severity=2,
                    asset_id="SUPPLY",
                    title=f"Low stock: {part['description']}",
                    detail=f"{part['qty']} on hand (min {part['min_qty']}), lead time {part['lead_days']}d",
                    actions=[
                        f"Re-order {part['part_id']} — ${part['unit_cost']:,} each",
                        f"Lead time: {part['lead_days']} days",
                    ],
                ))
        return recs

    # ── Sub-Agent: Compliance ──────────────────────────────────────

    def _compliance_agent(self, components: dict, sim: dict) -> list[Recommendation]:
        recs = []
        readings = sim.get("readings", {})

        # PHMSA / DOT compliance checks
        cp_readings = readings.get("CP-01", {})
        pipe_pot = cp_readings.get("PIPE_POT", -920)
        if pipe_pot > -850:
            recs.append(Recommendation(
                agent="COMPLIANCE",
                severity=3,
                asset_id="CP-01",
                title="NACE SP0169 / 49 CFR 195 non-compliance",
                detail=f"Pipe-to-soil potential {pipe_pot:.0f} mV — must be ≤ -850 mV",
                actions=[
                    "File PHMSA notification within 24 hours if persistent",
                    "Increase rectifier output immediately",
                    "Schedule close-interval survey (CIS) within 7 days",
                    "Document corrective actions per Integrity Management Plan",
                ],
            ))

        # Valve partial-stroke test overdue check (simulated)
        for vlv_id in ("VLV-01", "VLV-02", "VLV-03"):
            comp = components.get(vlv_id, {})
            if comp.get("health", 1.0) < 0.65:
                recs.append(Recommendation(
                    agent="COMPLIANCE",
                    severity=2,
                    asset_id=vlv_id,
                    title=f"{vlv_id} — partial-stroke test recommended",
                    detail="API 1160 / 49 CFR 195.420 requires valve operability verification",
                    actions=[
                        "Schedule partial-stroke test within next maintenance window",
                        "Verify actuator air/hydraulic supply",
                        "Document results in valve maintenance log",
                    ],
                ))
        return recs

    # ── 6th Agent: CREW ALLOCATION AGENT ─────────────────────────────

    def _auto_assign_crew(self, rec: Recommendation):
        """Agentic crew allocation: multi-crew dispatch with skill scoring,
        workload balancing, escalation logic, and reasoning chains."""
        if rec.severity < 2:
            return

        asset_id = rec.asset_id
        asset = next((a for a in ASSETS if a["asset_id"] == asset_id), None)
        if not asset:
            return
        asset_type = asset.get("type", "")

        # Step 1: Determine required crew roles from incident matrix
        crew_slots = INCIDENT_CREW_MATRIX.get((asset_type, rec.severity))
        if not crew_slots:
            # Fallback: single generic slot for unknown combos
            crew_slots = [{"role": "Responder", "certs": list(CERT_TO_ASSET.keys()), "required": True}]

        # Step 2: Build workload map (how many active assignments per crew member)
        workload: dict[str, int] = {}
        for ca in self.state.crew_assignments[-50:]:
            workload[ca.crew_name] = workload.get(ca.crew_name, 0) + 1

        # Step 3: Track who's already assigned to THIS incident (no double-booking)
        assigned_names: set[str] = set()

        # Step 4: Fill each crew slot using skill scoring + availability
        for slot in crew_slots:
            candidates = self._score_candidates(
                slot, asset_type, workload, assigned_names
            )
            if not candidates:
                if slot["required"]:
                    # No qualified crew — generate escalation
                    rec.actions.append(
                        f"ESCALATION: No available {slot['role']} with "
                        f"{'/'.join(slot['certs'][:3])} — call mutual aid"
                    )
                continue

            # Pick the best candidate (highest composite score)
            best = candidates[0]
            member, score, cert_match, eta, reasons = best

            ca = CrewAssignment(
                crew_name=member["name"],
                asset_id=asset_id,
                issue_type=rec.title,
                eta_min=eta,
                cert_reason=cert_match,
                role=slot["role"],
                skill_score=score,
                reasoning=" → ".join(reasons),
            )
            rec.crew.append(ca)
            self.state.crew_assignments.append(ca)
            assigned_names.add(member["name"])
            workload[member["name"]] = workload.get(member["name"], 0) + 1

    def _score_candidates(
        self, slot: dict, asset_type: str,
        workload: dict[str, int], exclude: set[str],
    ) -> list[tuple]:
        """Score and rank crew candidates for a given slot.
        Returns sorted list of (member, composite_score, best_cert, eta, reasoning)."""
        results = []

        for member in CREW:
            if member["name"] in exclude:
                continue

            # Check workload limit
            current_load = workload.get(member["name"], 0)
            if current_load >= MAX_CONCURRENT_ASSIGNMENTS:
                continue

            # Find best matching cert for this slot
            best_cert = None
            best_tier = 0
            for cert in member["certs"]:
                if cert in slot["certs"]:
                    tier = CERT_TIER.get(cert, 1)
                    if tier > best_tier:
                        best_tier = tier
                        best_cert = cert
                # Also check if cert covers the asset type (broader match)
                if not best_cert and cert in CERT_TO_ASSET:
                    if asset_type in CERT_TO_ASSET[cert]:
                        best_cert = cert
                        best_tier = max(1, CERT_TIER.get(cert, 1) - 1)

            if not best_cert:
                continue

            # Calculate ETA
            eta = ZONE_ETA.get(member["zone"], 15)
            if member["shift"] == "Night":
                eta += NIGHT_SHIFT_PENALTY

            # Composite score: skill_tier(0-30) + proximity(0-20) + availability(0-10)
            skill_score = best_tier * 10               # 10-30 points
            prox_score = max(0, 20 - eta)              # 0-20 points (closer = higher)
            avail_score = (MAX_CONCURRENT_ASSIGNMENTS - current_load) * 5  # 0-10 points
            composite = skill_score + prox_score + avail_score

            # Build reasoning chain
            reasons = [
                f"Cert match: {best_cert} (tier {best_tier})",
                f"ETA: {eta}min from {member['zone']}",
            ]
            if member["shift"] == "Night":
                reasons.append(f"Night shift (+{NIGHT_SHIFT_PENALTY}min)")
            if current_load > 0:
                reasons.append(f"Current load: {current_load} task(s)")
            reasons.append(f"Score: {composite} (skill:{skill_score} prox:{prox_score} avail:{avail_score})")

            results.append((member, composite, best_cert, eta, reasons))

        # Sort by composite score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ── Chat / NLU ─────────────────────────────────────────────────

    COMPONENT_ALIASES = {
        "segment":    ["SEG-01", "SEG-02", "SEG-03"],
        "seg":        ["SEG-01", "SEG-02", "SEG-03"],
        "pipe":       ["SEG-01", "SEG-02", "SEG-03"],
        "compressor": ["CS-01", "CS-02"],
        "pump":       ["PS-01", "PS-02"],
        "meter":      ["MET-01", "MET-02"],
        "pig":        ["PIG-01", "PIG-02"],
        "valve":      ["VLV-01", "VLV-02", "VLV-03"],
        "rtu":        ["RTU-01", "RTU-02", "RTU-03"],
        "scada":      ["RTU-01", "RTU-02", "RTU-03"],
        "cp":         ["CP-01"],
        "cathodic":   ["CP-01"],
    }

    INTENT_KEYWORDS = {
        "summary":          ["summary", "sitrep", "status", "what's happening", "overview", "brief"],
        "component_health": ["health", "condition", "sensor", "reading", "diagnostic"],
        "rul":              ["rul", "remaining useful", "predict", "fail", "probability", "life"],
        "work_orders":      ["work order", "wo ", "maintenance", "cmms", "sap"],
        "crew":             ["crew", "assign", "qualified", "technician", "who can"],
        "spare_parts":      ["spare", "part", "inventory", "stock", "supply"],
        "leak":             ["leak", "imbalance", "flow", "material balance"],
        "compliance":       ["compliance", "phmsa", "dot", "nace", "regulation", "cfr"],
        "operations":       ["operation", "throughput", "pig run", "shutdown", "restart"],
    }

    def handle_query(self, text: str) -> str:
        low = text.lower().strip()
        self.state.chat_history.append({"role": "user", "content": text})

        # Detect intent
        intent = "summary"
        for k, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in low for kw in keywords):
                intent = k
                break

        # Detect specific asset
        target_assets: list[str] = []
        for alias, aids in self.COMPONENT_ALIASES.items():
            if alias in low:
                target_assets = aids
                break
        # Direct asset ID match
        for a in ASSETS:
            if a["asset_id"].lower() in low:
                target_assets = [a["asset_id"]]
                break

        response = ""
        if intent == "summary":
            response = self._fmt_summary()
        elif intent == "component_health":
            response = self._fmt_component(target_assets)
        elif intent == "rul":
            response = self._fmt_rul(target_assets)
        elif intent == "work_orders":
            response = self._fmt_wo()
        elif intent == "crew":
            response = self._fmt_crew()
        elif intent == "spare_parts":
            response = self._fmt_parts()
        elif intent == "leak":
            response = self._fmt_leak()
        elif intent == "compliance":
            response = self._fmt_compliance()
        elif intent == "operations":
            response = self._fmt_operations()

        self.state.chat_history.append({"role": "assistant", "content": response})
        return response

    # ── Response Formatters ────────────────────────────────────────

    def _fmt_summary(self) -> str:
        recs = self.state.recommendations
        crit = sum(1 for r in recs[-20:] if r.severity == 3)
        warn = sum(1 for r in recs[-20:] if r.severity == 2)
        lines = [
            "## Pipeline Situation Report",
            "",
            f"**Active Alerts:** {crit} critical, {warn} warnings",
            f"**Recommendations:** {len(recs)} total",
            f"**Crew Deployed:** {len(self.state.crew_assignments)}",
            "",
        ]
        if recs:
            lines.append("**Latest Recommendations:**")
            for r in recs[-5:]:
                sev = "🔴" if r.severity == 3 else "🟡" if r.severity == 2 else "🟢"
                lines.append(f"- {sev} **[{r.agent}]** {r.title}")
        return "\n".join(lines)

    def _fmt_component(self, targets: list[str]) -> str:
        if not targets:
            targets = [a["asset_id"] for a in ASSETS[:5]]
        recs = self.state.recommendations
        lines = ["## Component Health Report", ""]
        for aid in targets:
            asset = next((a for a in ASSETS if a["asset_id"] == aid), None)
            if not asset:
                continue
            asset_recs = [r for r in recs[-20:] if r.asset_id == aid]
            lines.append(f"### {aid} — {asset.get('name', '')}")
            if asset_recs:
                for r in asset_recs[-3:]:
                    lines.append(f"- **[{r.severity_label}]** {r.title}")
                    for a in r.actions:
                        lines.append(f"  - {a}")
            else:
                lines.append("- No active alerts")
            lines.append("")
        return "\n".join(lines)

    def _fmt_rul(self, targets: list[str]) -> str:
        lines = ["## Remaining Useful Life Predictions", ""]
        preds = RUL_PREDICTIONS
        if targets:
            preds = [p for p in preds if p["asset_id"] in targets]
        for p in preds:
            lines.append(
                f"- **{p['asset_id']}**: {p['predicted_rul_days']} days "
                f"(7d: {p['failure_prob_7d']:.0%}, 30d: {p['failure_prob_30d']:.0%}) "
                f"[{p['model_version']}]"
            )
        return "\n".join(lines)

    def _fmt_wo(self) -> str:
        lines = ["## Work Orders", ""]
        for wo in WORK_ORDERS:
            st = wo["status"]
            icon = {"OPEN": "🔵", "IN_PROGRESS": "🟠", "PLANNED": "⚪", "COMPLETED": "✅"}.get(st, "⚪")
            lines.append(f"- {icon} **{wo['wo_id']}** [{wo['priority']}] {wo['title']} — {st}")
        return "\n".join(lines)

    def _fmt_crew(self) -> str:
        lines = ["## Crew Status", ""]
        # Build workload map
        workload: dict[str, int] = {}
        for ca in self.state.crew_assignments[-50:]:
            workload[ca.crew_name] = workload.get(ca.crew_name, 0) + 1

        for m in CREW:
            certs = ", ".join(m["certs"][:3])
            load = workload.get(m["name"], 0)
            status = f"🔴 {load} tasks" if load >= MAX_CONCURRENT_ASSIGNMENTS else (
                f"🟡 {load} task(s)" if load > 0 else "🟢 Available")
            lines.append(f"- **{m['name']}** ({m['role']}) — {m['shift']} shift, {m['zone']}")
            lines.append(f"  - Certs: {certs}")
            lines.append(f"  - Status: {status}")
        lines.append("")
        if self.state.crew_assignments:
            lines.append("**Active AI Dispatches (latest 8):**")
            for ca in self.state.crew_assignments[-8:]:
                role_str = f" [{ca.role}]" if ca.role else ""
                score_str = f" (score:{ca.skill_score})" if ca.skill_score else ""
                lines.append(f"- {ca.crew_name}{role_str} → {ca.asset_id} (ETA {ca.eta_min}min) — {ca.cert_reason}{score_str}")
                if ca.reasoning:
                    lines.append(f"  - *{ca.reasoning}*")
        return "\n".join(lines)

    def _fmt_parts(self) -> str:
        lines = ["## Spare Parts Inventory", ""]
        for p in SPARE_PARTS:
            flag = " ⚠️" if p["qty"] <= p["min_qty"] else ""
            lines.append(
                f"- **{p['part_id']}** {p['description']}: "
                f"{p['qty']} on hand (min {p['min_qty']}) — "
                f"${p['unit_cost']:,} ea, {p['lead_days']}d lead{flag}"
            )
        return "\n".join(lines)

    def _fmt_leak(self) -> str:
        leak_recs = [r for r in self.state.recommendations if r.agent == "LEAK_DETECT"]
        lines = ["## Leak Detection Summary", ""]
        if leak_recs:
            for r in leak_recs[-5:]:
                lines.append(f"### {r.title}")
                lines.append(f"{r.detail}")
                for a in r.actions:
                    lines.append(f"- {a}")
                lines.append("")
        else:
            lines.append("No active leak alarms. Material balance within tolerance.")
        return "\n".join(lines)

    def _fmt_compliance(self) -> str:
        comp_recs = [r for r in self.state.recommendations if r.agent == "COMPLIANCE"]
        lines = ["## Compliance Status", ""]
        if comp_recs:
            for r in comp_recs[-5:]:
                sev = "🔴" if r.severity == 3 else "🟡"
                lines.append(f"{sev} **{r.title}** ({r.asset_id})")
                for a in r.actions:
                    lines.append(f"- {a}")
                lines.append("")
        else:
            lines.append("All regulatory compliance checks passing.")
        return "\n".join(lines)

    def _fmt_operations(self) -> str:
        ops_recs = [r for r in self.state.recommendations if r.agent == "OPERATIONS"]
        lines = ["## Operations Report", ""]
        if ops_recs:
            for r in ops_recs[-5:]:
                lines.append(f"- **[{r.severity_label}]** {r.title}: {r.detail}")
        else:
            lines.append("Operations running normally. No escalations.")
        return "\n".join(lines)

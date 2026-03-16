import React, { useState, useEffect } from "react";

// ── Types ──────────────────────────────────────────────────
interface Mission {
  mission_id: string;
  asset_id: string;
  asset_type: string;
  status: string;
  start_ts: string;
  end_ts: string | null;
  summary_json: string | null;
}

// Pre-built demo report for MIS-DEMO-001
const DEMO_REPORTS: Record<string, any> = {
  "MIS-DEMO-001": {
    mission: { mission_id: "MIS-DEMO-001", asset_id: "Riser-A", asset_type: "riser", status: "completed", start_ts: "2026-03-14T10:00:00Z", end_ts: "2026-03-14T10:07:00Z" },
    drone: { drone_id: "DRONE-01", health: "normal", anomaly_score: 0.15, notes: "All subsystems nominal. Nav error within tolerance. No comms loss events." },
    issues: [
      { part: "Riser Clamp A3", defect: "Corrosion", severity: "high", confidence: 0.89, frames: ["FRM-002", "FRM-008"], metrics: { corrosion_pct: 12.5 }, action: "Schedule recoating within 30 days. Apply marine-grade epoxy per Section 4.2.1 of maintenance manual.", priority: 1, timeline: 30 },
      { part: "Riser Section 4", defect: "Coating Damage", severity: "medium", confidence: 0.78, frames: ["FRM-003"], metrics: { coating_loss_pct: 8.2 }, action: "Monitor on next inspection. Mark for recoat if area exceeds 15%.", priority: 3, timeline: 90 },
      { part: "Anode A1", defect: "Anode Depletion", severity: "medium", confidence: 0.85, frames: ["FRM-005"], metrics: { anode_util_pct: 72 }, action: "Plan anode replacement. Current utilization exceeds 70% threshold per CP survey procedures.", priority: 2, timeline: 60 },
      { part: "Weld Toe J5", defect: "Crack (Suspected)", severity: "high", confidence: 0.71, frames: ["FRM-006"], metrics: { crack_length_mm: 45 }, action: "URGENT: NDT follow-up required. Schedule UT thickness measurement and MPI within 14 days.", priority: 1, timeline: 14 },
      { part: "Riser Base", defect: "Marine Growth", severity: "low", confidence: 0.92, frames: ["FRM-004"], metrics: {}, action: "Routine cleaning recommended. No structural concern.", priority: 4, timeline: 180 },
    ],
    summary: { total_frames: 8, defects_found: 5, high_severity: 2, clean_frames: 3, avg_confidence: 0.83, mission_duration_min: 7 },
  },
  "MIS-DEMO-002": {
    mission: { mission_id: "MIS-DEMO-002", asset_id: "Manifold-B2", asset_type: "manifold", status: "completed", start_ts: "2026-03-14T09:00:00Z", end_ts: "2026-03-14T09:05:00Z" },
    drone: { drone_id: "DRONE-02", health: "warning", anomaly_score: 0.58, notes: "Thruster current elevated on port-bottom unit. RSSI degradation at depth >100m. Nav error spiked to 1.2m." },
    issues: [
      { part: "Manifold Flange B2", defect: "Corrosion", severity: "high", confidence: 0.91, frames: ["FRM-101", "FRM-105"], metrics: { corrosion_pct: 18.3 }, action: "CRITICAL: Flange integrity compromised. Schedule repair clamp installation within 7 days.", priority: 1, timeline: 7 },
      { part: "Weld Brace C1", defect: "Crack", severity: "high", confidence: 0.88, frames: ["FRM-103"], metrics: { crack_length_mm: 62 }, action: "URGENT: Confirmed fatigue crack. Initiate engineering assessment for repair or replacement.", priority: 1, timeline: 7 },
      { part: "Anode B2", defect: "Anode Depletion", severity: "medium", confidence: 0.79, frames: ["FRM-104"], metrics: { anode_util_pct: 85 }, action: "Schedule replacement. Anode near end-of-life. CP coverage may be insufficient.", priority: 2, timeline: 30 },
    ],
    summary: { total_frames: 5, defects_found: 3, high_severity: 2, clean_frames: 2, avg_confidence: 0.86, mission_duration_min: 5 },
  },
  "MIS-DEMO-004": {
    mission: { mission_id: "MIS-DEMO-004", asset_id: "Manifold-B2", asset_type: "manifold", status: "completed", start_ts: "2026-03-14T14:00:00Z", end_ts: "2026-03-14T14:20:00Z" },
    drone: { drone_id: "DRONE-02", health: "critical", anomaly_score: 0.92, notes: "CRITICAL: Thruster current reached 14.5A (limit 5A). Internal temps 44°C. Comms degraded to -92dBm. Mission auto-aborted due to anomaly threshold." },
    issues: [
      { part: "Manifold Valve V3", defect: "Corrosion", severity: "high", confidence: 0.94, frames: ["FRM-401", "FRM-405", "FRM-408"], metrics: { corrosion_pct: 22.1 }, action: "CRITICAL: Severe corrosion on valve body. Immediate isolation and replacement required.", priority: 1, timeline: 3 },
      { part: "Manifold Flange B2", defect: "Corrosion", severity: "high", confidence: 0.87, frames: ["FRM-402", "FRM-407"], metrics: { corrosion_pct: 15.8 }, action: "Flange corrosion progressing from previous inspection. Repair clamp installation overdue.", priority: 1, timeline: 7 },
      { part: "Anode Sled 2", defect: "Anode Depletion", severity: "high", confidence: 0.91, frames: ["FRM-404", "FRM-409"], metrics: { anode_util_pct: 93 }, action: "CRITICAL: Anodes near-fully consumed. CP system ineffective. Emergency replacement required.", priority: 1, timeline: 7 },
      { part: "Hub Connector H1", defect: "Coating Damage", severity: "medium", confidence: 0.76, frames: ["FRM-403"], metrics: { coating_loss_pct: 11.5 }, action: "Recoat at next opportunity. Exposed substrate will accelerate corrosion.", priority: 3, timeline: 30 },
      { part: "Support Bracket S2", defect: "Marine Growth", severity: "low", confidence: 0.88, frames: ["FRM-406"], metrics: {}, action: "Heavy fouling obscuring inspection targets. Cleaning required before next survey.", priority: 4, timeline: 60 },
      { part: "Pipe Spool PS-3", defect: "Crack (Suspected)", severity: "medium", confidence: 0.65, frames: ["FRM-410"], metrics: { crack_length_mm: 28 }, action: "Low confidence detection. Schedule focused NDT survey to confirm or dismiss.", priority: 2, timeline: 14 },
    ],
    summary: { total_frames: 10, defects_found: 6, high_severity: 3, clean_frames: 4, avg_confidence: 0.84, mission_duration_min: 20 },
  },
};

const sevColor = (s: string) => s === "high" ? "#ef4444" : s === "medium" ? "#eab308" : "#22c55e";
const statusColor = (s: string) => s === "completed" ? "#22c55e" : s === "in_progress" ? "#06b6d4" : s === "aborted" ? "#ef4444" : "#eab308";

export default function InspectionReportPage() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");

  useEffect(() => {
    fetch("/api/missions/recent").then(r => r.ok ? r.json() : []).then(setMissions).catch(() => {});
  }, []);

  const report = DEMO_REPORTS[selectedId];

  return (
    <div>
      <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>Inspection Report</h2>

      {/* Mission Selector */}
      <div style={card}>
        <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label style={labelStyle}>Select Mission</label>
            <select value={selectedId} onChange={e => setSelectedId(e.target.value)} style={inputStyle}>
              <option value="">— Choose a completed mission —</option>
              {Object.keys(DEMO_REPORTS).map(id => {
                const r = DEMO_REPORTS[id];
                return <option key={id} value={id}>{id} — {r.mission.asset_id} ({r.mission.asset_type}) — {r.mission.status}</option>;
              })}
              {missions.filter(m => !DEMO_REPORTS[m.mission_id]).map(m => (
                <option key={m.mission_id} value={m.mission_id}>{m.mission_id} — {m.asset_id} ({m.asset_type}) — {m.status}</option>
              ))}
            </select>
          </div>
          {report && (
            <div style={{ display: "flex", gap: 8 }}>
              <span style={{ padding: "6px 14px", borderRadius: 5, fontSize: 14, fontWeight: 700, background: statusColor(report.mission.status) + "22", color: statusColor(report.mission.status), border: `1px solid ${statusColor(report.mission.status)}55` }}>
                {report.mission.status.toUpperCase()}
              </span>
            </div>
          )}
        </div>
      </div>

      {!report && selectedId && (
        <div style={{ ...card, marginTop: 14, textAlign: "center", color: "#64748b", padding: 40 }}>
          No detailed report available for this mission. Select a demo mission (MIS-DEMO-001, 002, or 004).
        </div>
      )}

      {report && (
        <>
          {/* KPI Summary */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, marginTop: 14 }}>
            <KPI label="FRAMES" value={`${report.summary.total_frames}`} color="#06b6d4" />
            <KPI label="DEFECTS" value={`${report.summary.defects_found}`} color="#f97316" />
            <KPI label="HIGH SEV" value={`${report.summary.high_severity}`} color="#ef4444" />
            <KPI label="CLEAN" value={`${report.summary.clean_frames}`} color="#22c55e" />
            <KPI label="AVG CONF" value={`${(report.summary.avg_confidence * 100).toFixed(0)}%`} color="#a78bfa" />
            <KPI label="DURATION" value={`${report.summary.mission_duration_min}m`} color="#64748b" />
          </div>

          {/* Drone Health */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 14 }}>
            <div style={card}>
              <h3 style={sectionTitle}>Mission Details</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
                <StatRow label="Mission ID" value={report.mission.mission_id} />
                <StatRow label="Asset" value={`${report.mission.asset_id} (${report.mission.asset_type})`} />
                <StatRow label="Start" value={report.mission.start_ts?.slice(0, 16)} />
                <StatRow label="End" value={report.mission.end_ts?.slice(0, 16) || "In progress"} />
              </div>
            </div>
            <div style={card}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={sectionTitle}>Drone Health</h3>
                <span style={{ padding: "4px 12px", borderRadius: 5, fontSize: 13, fontWeight: 700, background: (report.drone.health === "normal" ? "#22c55e" : report.drone.health === "warning" ? "#eab308" : "#ef4444") + "22", color: report.drone.health === "normal" ? "#22c55e" : report.drone.health === "warning" ? "#eab308" : "#ef4444" }}>
                  {report.drone.health.toUpperCase()}
                </span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
                <StatRow label="Drone" value={report.drone.drone_id} />
                <StatRow label="Anomaly Score" value={report.drone.anomaly_score.toFixed(2)} color={report.drone.anomaly_score > 0.5 ? "#ef4444" : "#22c55e"} />
              </div>
              <p style={{ fontSize: 13, color: "#94a3b8", marginTop: 8, lineHeight: 1.6 }}>{report.drone.notes}</p>
            </div>
          </div>

          {/* Issues */}
          <div style={{ ...card, marginTop: 14 }}>
            <h3 style={sectionTitle}>Defects Found ({report.issues.length})</h3>
            {report.issues.sort((a: any, b: any) => a.priority - b.priority).map((issue: any, i: number) => (
              <div key={i} style={{ marginTop: 12, background: "#0e1624", border: "1px solid #1E2D4F", borderRadius: 6, padding: 14, borderLeft: `4px solid ${sevColor(issue.severity)}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0" }}>{issue.part}</span>
                    <span style={{ fontSize: 14, color: "#64748b", marginLeft: 10 }}>{issue.defect}</span>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: 12, color: "#64748b" }}>P{issue.priority}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: sevColor(issue.severity), textTransform: "uppercase" }}>{issue.severity}</span>
                    <span style={{ fontSize: 12, color: "#94a3b8" }}>{(issue.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>

                {/* Metrics */}
                <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
                  {issue.metrics.corrosion_pct != null && <Metric label="Corrosion Area" value={`${issue.metrics.corrosion_pct}%`} />}
                  {issue.metrics.coating_loss_pct != null && <Metric label="Coating Loss" value={`${issue.metrics.coating_loss_pct}%`} />}
                  {issue.metrics.anode_util_pct != null && <Metric label="Anode Used" value={`${issue.metrics.anode_util_pct}%`} />}
                  {issue.metrics.crack_length_mm != null && <Metric label="Crack Length" value={`${issue.metrics.crack_length_mm}mm`} />}
                </div>

                <div style={{ fontSize: 12, color: "#64748b", marginTop: 6 }}>Evidence: {issue.frames.join(", ")}</div>

                {/* Recommended Action */}
                <div style={{ marginTop: 8, padding: "8px 12px", background: "#0B0F1A", borderRadius: 4, borderLeft: `2px solid ${sevColor(issue.severity)}` }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 2 }}>RECOMMENDED ACTION (within {issue.timeline} days)</div>
                  <div style={{ fontSize: 14, color: "#e2e8f0", lineHeight: 1.5 }}>{issue.action}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Next Steps Summary */}
          <div style={{ ...card, marginTop: 14, borderLeft: "3px solid #06b6d4" }}>
            <h3 style={sectionTitle}>Recommended Next Steps</h3>
            <table style={{ width: "100%", marginTop: 10, borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Priority", "Action", "Asset Part", "Timeline", "Severity"].map(h => (
                    <th key={h} style={{ textAlign: "left", fontSize: 12, fontWeight: 700, color: "#64748b", padding: "6px 8px", borderBottom: "1px solid #1E2D4F" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {report.issues.sort((a: any, b: any) => a.priority - b.priority).map((issue: any, i: number) => (
                  <tr key={i}>
                    <td style={tdStyle}><span style={{ display: "inline-block", width: 24, height: 24, lineHeight: "24px", textAlign: "center", borderRadius: "50%", fontSize: 13, fontWeight: 700, background: issue.priority === 1 ? "#ef444422" : "#1E2D4F", color: issue.priority === 1 ? "#ef4444" : "#94a3b8" }}>{issue.priority}</span></td>
                    <td style={{ ...tdStyle, color: "#e2e8f0", fontWeight: 600 }}>{issue.action.split(".")[0]}.</td>
                    <td style={tdStyle}>{issue.part}</td>
                    <td style={tdStyle}>{issue.timeline <= 7 ? "Urgent" : issue.timeline <= 30 ? "Planned" : "Monitor"} <span style={{ color: "#64748b" }}>({issue.timeline}d)</span></td>
                    <td style={tdStyle}><span style={{ color: sevColor(issue.severity), fontWeight: 700, textTransform: "uppercase" }}>{issue.severity}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!selectedId && (
        <div style={{ ...card, marginTop: 14, textAlign: "center", color: "#64748b", padding: 50 }}>
          Select a mission above to view the inspection report with defect analysis and recommended actions.
        </div>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────

function KPI({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "#141B2D", border: "1px solid #1E2D4F", borderRadius: 6, padding: "10px 12px", borderTop: `2px solid ${color}`, textAlign: "center" }}>
      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function StatRow({ label, value, color = "#e2e8f0" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: "#0B0F1A", borderRadius: 4, padding: "6px 10px" }}>
      <div style={{ fontSize: 11, color: "#64748b" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "#64748b" }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "#e2e8f0" }}>{value}</div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────
const card: React.CSSProperties = { background: "#141B2D", border: "1px solid #1E2D4F", borderRadius: 8, padding: 20 };
const labelStyle: React.CSSProperties = { display: "block", fontSize: 13, fontWeight: 600, color: "#64748b", marginBottom: 4 };
const inputStyle: React.CSSProperties = { width: "100%", padding: "10px 14px", borderRadius: 4, border: "1px solid #1E2D4F", background: "#0B0F1A", color: "#e2e8f0", fontSize: 15 };
const sectionTitle: React.CSSProperties = { fontSize: 18, fontWeight: 700, color: "#e2e8f0" };
const tdStyle: React.CSSProperties = { fontSize: 13, color: "#94a3b8", padding: "8px", borderBottom: "1px solid #1E2D4F", verticalAlign: "top", lineHeight: 1.5 };

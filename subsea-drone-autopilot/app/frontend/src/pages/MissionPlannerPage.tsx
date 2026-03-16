import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";

// ── Types ──────────────────────────────────────────────────
interface MissionPlan {
  mission_id: string | null;
  selected_drone: string | null;
  status: string;
  plan: {
    asset_id: string;
    asset_type: string;
    target_depth_m: number | null;
    depth_range_m: { min: number | null; max: number | null };
    inspection_type: string;
    risk_level: string;
    environment: {
      sea_state: string;
      current_speed_knots: number | null;
      visibility_m: number | null;
    };
    drone_limits: {
      max_depth_m: number;
      max_duration_min: number;
      min_battery_reserve_pct: number;
    };
    estimated: {
      duration_min: number;
      distance_m: number;
      battery_use_pct: number;
      battery_reserve_pct: number;
    };
    waypoints: { lat: number | null; lon: number | null; depth_m: number }[];
    safety_checks: string[];
    constraints: string[];
    objectives: string[];
  } | null;
  summary: string;
}

// ── Component ──────────────────────────────────────────────
export default function MissionPlannerPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    asset_id: "Riser-A",
    asset_type: "riser",
    target_depth_m: "120",
    inspection_type: "visual_clamps",
    risk_level: "medium",
    notes: "",
  });
  const [logs, setLogs] = useState<string[]>([]);
  const [result, setResult] = useState<MissionPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => setForm({ ...form, [e.target.name]: e.target.value });

  // ── Streaming submit ─────────────────────────────────────
  const handleSubmitStream = async () => {
    setLoading(true);
    setLogs([]);
    setResult(null);

    const body = {
      asset_id: form.asset_id,
      asset_type: form.asset_type,
      target_depth_m: form.target_depth_m ? parseFloat(form.target_depth_m) : null,
      inspection_type: form.inspection_type,
      risk_level: form.risk_level,
      notes: form.notes,
    };

    try {
      const resp = await fetch("/api/autopilot/plan-and-launch/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!resp.ok || !resp.body) {
        setLogs((prev) => [...prev, `Error: HTTP ${resp.status}`]);
        setLoading(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              if (currentEvent === "status") {
                setLogs((prev) => [...prev, data.message || "Processing..."]);
              } else if (currentEvent === "final") {
                if (data.status === "error") {
                  setLogs((prev) => [...prev, `Error: ${data.summary || "Agent failed"}`]);
                } else {
                  setResult(data as MissionPlan);
                }
                setLoading(false);
              }
            } catch {
              setLogs((prev) => [...prev, line.slice(5).trim()]);
            }
          }
        }
      }
    } catch (err: any) {
      setLogs((prev) => [...prev, `Stream error: ${err?.message || err}`]);
    }
    setLoading(false);
  };

  // ── Sync submit ──────────────────────────────────────────
  const handleSubmitSync = async () => {
    setLoading(true);
    setLogs(["Sending to autopilot (sync)..."]);
    setResult(null);

    const body = {
      asset_id: form.asset_id,
      asset_type: form.asset_type,
      target_depth_m: form.target_depth_m ? parseFloat(form.target_depth_m) : null,
      inspection_type: form.inspection_type,
      risk_level: form.risk_level,
      notes: form.notes,
    };

    const resp = await fetch("/api/autopilot/plan-and-launch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    setResult(data as MissionPlan);
    setLogs((prev) => [...prev, "Done."]);
    setLoading(false);
  };

  // ── Status badge color ──────────────────────────────────
  const statusColor = (s: string) =>
    s === "launched"
      ? "#22c55e"
      : s === "planned"
      ? "#3b82f6"
      : s === "refused"
      ? "#ef4444"
      : "#eab308";

  // ── Render ───────────────────────────────────────────────
  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>
        Mission Planner
      </h2>

      {/* Form */}
      <div style={card}>
        <div style={grid}>
          <Field label="Asset ID">
            <input name="asset_id" value={form.asset_id} onChange={handleChange} style={input} />
          </Field>
          <Field label="Asset Type">
            <select name="asset_type" value={form.asset_type} onChange={handleChange} style={input}>
              <option value="riser">Riser</option>
              <option value="mooring">Mooring</option>
              <option value="manifold">Manifold</option>
              <option value="flowline">Flowline</option>
              <option value="fpso_hull">FPSO Hull</option>
            </select>
          </Field>
          <Field label="Target Depth (m)">
            <input
              name="target_depth_m"
              type="number"
              value={form.target_depth_m}
              onChange={handleChange}
              style={input}
            />
          </Field>
          <Field label="Inspection Type">
            <select
              name="inspection_type"
              value={form.inspection_type}
              onChange={handleChange}
              style={input}
            >
              <option value="visual_clamps">Visual – Clamps</option>
              <option value="visual_general">Visual – General</option>
              <option value="ndt_thickness">NDT – Thickness</option>
              <option value="cathodic_protection">Cathodic Protection</option>
              <option value="marine_growth">Marine Growth</option>
            </select>
          </Field>
          <Field label="Risk Level">
            <select name="risk_level" value={form.risk_level} onChange={handleChange} style={input}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </Field>
        </div>
        <Field label="Notes">
          <textarea
            name="notes"
            value={form.notes}
            onChange={handleChange}
            rows={2}
            style={{ ...input, resize: "vertical" }}
          />
        </Field>

        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button onClick={handleSubmitStream} disabled={loading} style={btnPrimary}>
            {loading ? "Running..." : "Plan & Launch (Stream)"}
          </button>
          <button onClick={handleSubmitSync} disabled={loading} style={btnSecondary}>
            Plan & Launch (Sync)
          </button>
        </div>
      </div>

      {/* Autopilot Log */}
      {logs.length > 0 && (
        <div style={{ ...card, marginTop: 16 }}>
          <h3 style={sectionTitle}>Autopilot Log</h3>
          <div style={logBox}>
            {logs.map((l, i) => (
              <div key={i} style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.6 }}>
                <span style={{ color: "#06b6d4" }}>&gt;</span> {l}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div style={{ ...card, marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={sectionTitle}>Mission Result</h3>
            <span
              style={{
                padding: "3px 10px",
                borderRadius: 4,
                fontSize: 14,
                fontWeight: 700,
                background: statusColor(result.status) + "22",
                color: statusColor(result.status),
                border: `1px solid ${statusColor(result.status)}55`,
              }}
            >
              {result.status.toUpperCase()}
            </span>
          </div>

          <div style={{ ...grid, marginTop: 12 }}>
            <Stat label="Mission ID" value={result.mission_id || "—"} />
            <Stat label="Drone" value={result.selected_drone || "—"} />
            {result.plan?.estimated && (
              <>
                <Stat label="Est. Duration" value={`${result.plan.estimated.duration_min.toFixed(0)} min`} />
                <Stat label="Est. Distance" value={`${result.plan.estimated.distance_m.toFixed(0)} m`} />
                <Stat label="Battery Use" value={`${result.plan.estimated.battery_use_pct.toFixed(1)}%`} />
                <Stat
                  label="Battery Reserve"
                  value={`${result.plan.estimated.battery_reserve_pct.toFixed(1)}%`}
                />
              </>
            )}
          </div>

          {/* Safety Checks */}
          {result.plan?.safety_checks && result.plan.safety_checks.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#64748b", marginBottom: 4 }}>
                SAFETY CHECKS
              </div>
              {result.plan.safety_checks.map((c, i) => (
                <div key={i} style={{ fontSize: 14, color: "#22c55e", lineHeight: 1.6 }}>
                  &#x2713; {c}
                </div>
              ))}
            </div>
          )}

          <p style={{ fontSize: 15, color: "#94a3b8", marginTop: 12, lineHeight: 1.5 }}>
            {result.summary}
          </p>

          {result.status === "launched" && result.mission_id && (
            <button
              onClick={() => navigate(`/live/${result.mission_id}`)}
              style={{ ...btnPrimary, marginTop: 12, fontSize: 14 }}
            >
              Go to Live Viewer &rarr;
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "#64748b", marginBottom: 4 }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#0e1624", borderRadius: 6, padding: "8px 12px", border: "1px solid #1E2D4F" }}>
      <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "#e2e8f0", marginTop: 2 }}>{value}</div>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: "#141B2D",
  border: "1px solid #1E2D4F",
  borderRadius: 8,
  padding: 20,
};
const grid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
  gap: 12,
};
const input: React.CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  borderRadius: 4,
  border: "1px solid #1E2D4F",
  background: "#0B0F1A",
  color: "#e2e8f0",
  fontSize: 15,
};
const btnPrimary: React.CSSProperties = {
  padding: "10px 20px",
  borderRadius: 6,
  border: "none",
  background: "#06b6d4",
  color: "#0B0F1A",
  fontWeight: 700,
  fontSize: 15,
  cursor: "pointer",
};
const btnSecondary: React.CSSProperties = {
  ...btnPrimary,
  background: "#1E2D4F",
  color: "#94a3b8",
};
const sectionTitle: React.CSSProperties = {
  fontSize: 18,
  fontWeight: 700,
  color: "#e2e8f0",
};
const logBox: React.CSSProperties = {
  marginTop: 8,
  background: "#0B0F1A",
  borderRadius: 4,
  padding: 10,
  maxHeight: 180,
  overflowY: "auto",
  border: "1px solid #1E2D4F",
};

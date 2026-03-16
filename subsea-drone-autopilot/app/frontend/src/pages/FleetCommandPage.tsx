import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

// ── Types ──────────────────────────────────────────────────
interface DroneData {
  drone_id: string;
  depth_m: number;
  battery_pct: number;
  health_score: number;
  anomaly_score: number;
  state: string;
  mission_id: string | null;
  thruster_currents: number[];
  internal_temps_c: number[];
  network_rssi_dbm: number;
  nav_error_m: number;
  imu_roll_deg: number;
  imu_pitch_deg: number;
  battery_draw_w: number;
}

interface Environment {
  sea_state: string;
  wave_height_m: number;
  current_speed_knots: number;
  current_direction_deg: number;
  visibility_m: number;
  water_temp_c: number;
  weather: string;
}

interface FleetSummary {
  tick: number;
  environment: Environment;
  fleet: {
    total: number;
    operational: number;
    in_mission: number;
    grounded: number;
    avg_health: number;
    avg_battery: number;
    total_anomalies: number;
  };
  drones: Record<string, DroneData>;
}

// ── Component ──────────────────────────────────────────────
// ── Ocean Map ──────────────────────────────────────────────
// Subsea asset locations in Gulf Location (lat/lon → SVG coords)
const MAP_ASSETS = [
  { id: "Riser-A", type: "riser", lat: 28.42, lon: -89.15, label: "Riser-A" },
  { id: "Riser-B", type: "riser", lat: 28.38, lon: -89.22, label: "Riser-B" },
  { id: "Riser-C", type: "riser", lat: 28.45, lon: -89.08, label: "Riser-C" },
  { id: "Riser-D", type: "riser", lat: 28.35, lon: -89.30, label: "Riser-D" },
  { id: "Manifold-B1", type: "manifold", lat: 28.40, lon: -89.18, label: "Mfld-B1" },
  { id: "Manifold-B2", type: "manifold", lat: 28.37, lon: -89.25, label: "Mfld-B2" },
  { id: "Manifold-B3", type: "manifold", lat: 28.43, lon: -89.12, label: "Mfld-B3" },
  { id: "Flowline-5", type: "flowline", lat: 28.39, lon: -89.20, label: "FL-5" },
  { id: "Flowline-7", type: "flowline", lat: 28.41, lon: -89.10, label: "FL-7" },
  { id: "Flowline-12", type: "flowline", lat: 28.36, lon: -89.28, label: "FL-12" },
  { id: "FPSO-Hull-P1", type: "fpso", lat: 28.44, lon: -89.05, label: "FPSO-P1" },
  { id: "Mooring-N1", type: "mooring", lat: 28.46, lon: -89.07, label: "Moor-N1" },
  { id: "Mooring-N2", type: "mooring", lat: 28.43, lon: -89.03, label: "Moor-N2" },
];

const ASSET_COLORS: Record<string, string> = {
  riser: "#3b82f6", manifold: "#f97316", flowline: "#a78bfa",
  fpso: "#22c55e", mooring: "#eab308",
};

// Drone positions (simulated around assets)
const DRONE_POSITIONS: Record<string, { lat: number; lon: number }> = {
  "DRONE-01": { lat: 28.42, lon: -89.14 },
  "DRONE-02": { lat: 28.37, lon: -89.24 }, // at Manifold-B2
  "DRONE-03": { lat: 28.48, lon: -89.02 }, // docked/maintenance
  "DRONE-04": { lat: 28.44, lon: -89.06 },
  "DRONE-05": { lat: 28.40, lon: -89.19 },
};

function OceanMap({ drones, tick }: { drones: DroneData[]; tick: number }) {
  // Map bounds (Gulf Location zoom)
  const latMin = 28.30, latMax = 28.52, lonMin = -89.38, lonMax = -88.95;
  const W = 460, H = 260;

  const toX = (lon: number) => ((lon - lonMin) / (lonMax - lonMin)) * W;
  const toY = (lat: number) => ((latMax - lat) / (latMax - latMin)) * H;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", borderRadius: 6 }}>
      {/* Ocean background */}
      <defs>
        <radialGradient id="ocean-bg" cx="50%" cy="50%" r="70%">
          <stop offset="0%" stopColor="#0c2d48" />
          <stop offset="100%" stopColor="#071525" />
        </radialGradient>
        <filter id="glow-sm">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <rect width={W} height={H} fill="url(#ocean-bg)" rx="6" />

      {/* Grid */}
      {[0.25, 0.5, 0.75].map((p) => (
        <g key={p} opacity="0.15">
          <line x1={W * p} y1="0" x2={W * p} y2={H} stroke="#1e3a5f" />
          <line x1="0" y1={H * p} x2={W} y2={H * p} stroke="#1e3a5f" />
        </g>
      ))}

      {/* Lat/Lon labels */}
      <text x="4" y="12" fill="#1e3a5f" fontSize="7" fontFamily="monospace">28.50°N</text>
      <text x="4" y={H - 4} fill="#1e3a5f" fontSize="7" fontFamily="monospace">28.30°N</text>
      <text x={W - 50} y={H - 4} fill="#1e3a5f" fontSize="7" fontFamily="monospace">89.00°W</text>
      <text x="4" y={H - 14} fill="#1e3a5f" fontSize="7" fontFamily="monospace">Gulf Block 42</text>

      {/* Flowline connections (between related assets) */}
      {[
        ["Riser-A", "Manifold-B1"], ["Riser-B", "Manifold-B2"], ["Riser-C", "Manifold-B3"],
        ["Manifold-B1", "Flowline-5"], ["Manifold-B2", "Flowline-12"],
        ["Riser-C", "Flowline-7"], ["FPSO-Hull-P1", "Mooring-N1"], ["FPSO-Hull-P1", "Mooring-N2"],
      ].map(([a, b], i) => {
        const pa = MAP_ASSETS.find((x) => x.id === a);
        const pb = MAP_ASSETS.find((x) => x.id === b);
        if (!pa || !pb) return null;
        return (
          <line key={i} x1={toX(pa.lon)} y1={toY(pa.lat)} x2={toX(pb.lon)} y2={toY(pb.lat)}
            stroke="#1e3a5f" strokeWidth="1" strokeDasharray="3 3" opacity="0.4" />
        );
      })}

      {/* Assets */}
      {MAP_ASSETS.map((a) => {
        const x = toX(a.lon), y = toY(a.lat);
        const c = ASSET_COLORS[a.type] || "#64748b";
        return (
          <g key={a.id}>
            {a.type === "fpso" ? (
              <rect x={x - 8} y={y - 4} width="16" height="8" rx="2" fill={c} opacity="0.7" />
            ) : a.type === "flowline" ? (
              <rect x={x - 5} y={y - 2} width="10" height="4" rx="1" fill={c} opacity="0.6" />
            ) : (
              <circle cx={x} cy={y} r={a.type === "manifold" ? 5 : 4} fill={c} opacity="0.6" />
            )}
            <text x={x} y={y - 7} textAnchor="middle" fill={c} fontSize="6" fontFamily="monospace" opacity="0.8">
              {a.label}
            </text>
          </g>
        );
      })}

      {/* Drones */}
      {drones.map((d) => {
        const pos = DRONE_POSITIONS[d.drone_id];
        if (!pos) return null;
        const x = toX(pos.lon), y = toY(pos.lat);
        const sc = d.state === "idle" ? "#22c55e" : d.state === "in_mission" ? "#06b6d4"
          : d.state === "maintenance" ? "#ef4444" : "#eab308";

        // Animate active drones with a pulse ring
        const isActive = d.state === "in_mission";

        return (
          <g key={d.drone_id} filter={isActive ? "url(#glow-sm)" : undefined}>
            {/* Sonar ping ring for active */}
            {isActive && (
              <circle cx={x} cy={y} r={10 + (tick % 20)} fill="none" stroke={sc}
                strokeWidth="0.5" opacity={Math.max(0, 0.4 - (tick % 20) * 0.02)} />
            )}
            {/* Drone icon — small ROV shape */}
            <ellipse cx={x} cy={y} rx="6" ry="3" fill={sc} opacity="0.9" />
            <circle cx={x + 4} cy={y} r="1.5" fill="#fff" opacity="0.6" />
            {/* Label */}
            <text x={x} y={y + 10} textAnchor="middle" fill={sc} fontSize="6.5"
              fontFamily="monospace" fontWeight="bold">
              {d.drone_id.replace("DRONE-0", "D")}
            </text>
            {/* Depth badge for submerged */}
            {d.depth_m > 1 && (
              <text x={x} y={y + 17} textAnchor="middle" fill="#06b6d4" fontSize="5.5" fontFamily="monospace">
                {d.depth_m.toFixed(0)}m
              </text>
            )}
          </g>
        );
      })}

      {/* Legend */}
      <g transform={`translate(${W - 100}, 8)`}>
        <rect x="-4" y="-4" width="100" height="70" rx="3" fill="#0B0F1A" opacity="0.7" />
        {[
          ["riser", "Riser"], ["manifold", "Manifold"], ["flowline", "Flowline"],
          ["fpso", "FPSO"], ["mooring", "Mooring"],
        ].map(([type, label], i) => (
          <g key={type} transform={`translate(0, ${i * 13})`}>
            <circle cx="4" cy="3" r="3" fill={ASSET_COLORS[type]} opacity="0.7" />
            <text x="12" y="6" fill="#94a3b8" fontSize="6.5" fontFamily="monospace">{label}</text>
          </g>
        ))}
        <g transform="translate(0, 65)">
          <ellipse cx="4" cy="0" rx="5" ry="2.5" fill="#06b6d4" opacity="0.9" />
          <text x="12" y="3" fill="#94a3b8" fontSize="6.5" fontFamily="monospace">Drone</text>
        </g>
      </g>

      {/* Title */}
      <text x="8" y="20" fill="#e2e8f0" fontSize="9" fontWeight="bold" fontFamily="monospace">
        OPERATIONS MAP — Gulf Location
      </text>
    </svg>
  );
}

// ── Drone Technical Spec Panel (blueprint wireframe) ───────
function DroneSpecPanel() {
  const [expanded, setExpanded] = useState(true);

  return (
    <div style={{ background: "#141B2D", border: "1px solid #1E2D4F", borderRadius: 8, marginBottom: 12, overflow: "hidden" }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", cursor: "pointer" }}
      >
        <span style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0" }}>
          Vehicle Specification — Subsea Explorer AUV/ROV Hybrid
        </span>
        <span style={{ fontSize: 11, color: "#64748b" }}>{expanded ? "Collapse" : "Expand"}</span>
      </div>

      {expanded && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0, borderTop: "1px solid #1E2D4F" }}>
          {/* Left: Blueprint wireframe SVG */}
          <div style={{ padding: 16 }}>
            <svg viewBox="0 0 520 360" width="100%" style={{ display: "block" }}>
              {/* Blueprint background */}
              <rect width="520" height="360" fill="#071320" rx="4" />
              {/* Grid */}
              {Array.from({length: 26}, (_, i) => <line key={`vg${i}`} x1={i*20} y1="0" x2={i*20} y2="360" stroke="#0d2240" strokeWidth="0.5" />)}
              {Array.from({length: 18}, (_, i) => <line key={`hg${i}`} x1="0" y1={i*20} x2="520" y2={i*20} stroke="#0d2240" strokeWidth="0.5" />)}

              {/* Title block */}
              <rect x="4" y="4" width="260" height="22" fill="#0d1b30" rx="2" />
              <text x="10" y="18" fill="#06b6d4" fontSize="9" fontWeight="bold" fontFamily="monospace">GENERAL ARRANGEMENT — SIDE VIEW</text>
              <rect x="4" y="334" width="512" height="22" fill="#0d1b30" rx="2" />
              <text x="10" y="349" fill="#4a5568" fontSize="7" fontFamily="monospace">DWG: ROV-GA-001 REV.C | SCALE: NTS | CLASSIFICATION: UNRESTRICTED | ALL DIMENSIONS IN MM</text>

              {/* === ROV WIREFRAME (side view) === */}
              <g transform="translate(260, 170)">
                {/* Main frame/hull outline */}
                <rect x="-140" y="-45" width="280" height="90" rx="20" fill="none" stroke="#06b6d4" strokeWidth="1.5" />
                {/* Internal structure lines */}
                <line x1="-100" y1="-45" x2="-100" y2="45" stroke="#06b6d4" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.4" />
                <line x1="-40" y1="-45" x2="-40" y2="45" stroke="#06b6d4" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.4" />
                <line x1="40" y1="-45" x2="40" y2="45" stroke="#06b6d4" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.4" />
                <line x1="100" y1="-45" x2="100" y2="45" stroke="#06b6d4" strokeWidth="0.5" strokeDasharray="3 3" opacity="0.4" />

                {/* Buoyancy foam (top) */}
                <rect x="-120" y="-60" width="240" height="18" rx="4" fill="none" stroke="#22c55e" strokeWidth="1" strokeDasharray="4 2" />
                <text x="0" y="-67" textAnchor="middle" fill="#22c55e" fontSize="6" fontFamily="monospace">SYNTACTIC FOAM BUOYANCY</text>

                {/* Forward camera dome */}
                <circle cx="150" cy="0" r="18" fill="none" stroke="#3b82f6" strokeWidth="1.2" />
                <circle cx="150" cy="0" r="8" fill="none" stroke="#3b82f6" strokeWidth="0.8" />
                <circle cx="150" cy="0" r="3" fill="#3b82f6" opacity="0.3" />
                {/* Secondary cameras */}
                <circle cx="140" cy="-30" r="6" fill="none" stroke="#3b82f6" strokeWidth="0.8" />
                <circle cx="140" cy="30" r="6" fill="none" stroke="#3b82f6" strokeWidth="0.8" />

                {/* Forward lights */}
                <ellipse cx="130" cy="-38" rx="8" ry="4" fill="none" stroke="#eab308" strokeWidth="0.8" />
                <ellipse cx="130" cy="38" rx="8" ry="4" fill="none" stroke="#eab308" strokeWidth="0.8" />

                {/* Horizontal thrusters (port/stbd) */}
                <rect x="-155" y="-20" width="20" height="16" rx="4" fill="none" stroke="#f97316" strokeWidth="1" />
                <line x1="-145" y1="-12" x2="-145" y2="-12" stroke="#f97316" strokeWidth="0" />
                <ellipse cx="-145" cy="-12" rx="6" ry="6" fill="none" stroke="#f97316" strokeWidth="0.5" strokeDasharray="2 2" />
                <rect x="-155" y="4" width="20" height="16" rx="4" fill="none" stroke="#f97316" strokeWidth="1" />
                <ellipse cx="-145" cy="12" rx="6" ry="6" fill="none" stroke="#f97316" strokeWidth="0.5" strokeDasharray="2 2" />

                {/* Stern thrusters */}
                <rect x="135" y="-20" width="20" height="16" rx="4" fill="none" stroke="#f97316" strokeWidth="1" />
                <ellipse cx="145" cy="-12" rx="6" ry="6" fill="none" stroke="#f97316" strokeWidth="0.5" strokeDasharray="2 2" />
                <rect x="135" y="4" width="20" height="16" rx="4" fill="none" stroke="#f97316" strokeWidth="1" />
                <ellipse cx="145" cy="12" rx="6" ry="6" fill="none" stroke="#f97316" strokeWidth="0.5" strokeDasharray="2 2" />

                {/* Vertical thrusters */}
                <rect x="-60" y="-62" width="14" height="20" rx="3" fill="none" stroke="#a78bfa" strokeWidth="1" />
                <rect x="46" y="-62" width="14" height="20" rx="3" fill="none" stroke="#a78bfa" strokeWidth="1" />

                {/* Manipulator arm */}
                <line x1="-120" y1="45" x2="-140" y2="70" stroke="#ef4444" strokeWidth="2" />
                <line x1="-140" y1="70" x2="-125" y2="90" stroke="#ef4444" strokeWidth="1.5" />
                <line x1="-125" y1="90" x2="-115" y2="88" stroke="#ef4444" strokeWidth="1" />
                <line x1="-125" y1="90" x2="-120" y2="95" stroke="#ef4444" strokeWidth="1" />
                <circle cx="-140" cy="70" r="3" fill="none" stroke="#ef4444" strokeWidth="0.8" />
                <circle cx="-125" cy="90" r="2" fill="none" stroke="#ef4444" strokeWidth="0.8" />

                {/* Sonar dome (bottom) */}
                <ellipse cx="0" cy="52" rx="25" ry="8" fill="none" stroke="#a78bfa" strokeWidth="1" strokeDasharray="3 2" />

                {/* Battery compartment */}
                <rect x="-90" y="-30" width="45" height="60" rx="3" fill="none" stroke="#eab308" strokeWidth="0.8" strokeDasharray="4 2" />

                {/* Electronics housing */}
                <rect x="-30" y="-30" width="55" height="60" rx="3" fill="none" stroke="#06b6d4" strokeWidth="0.8" strokeDasharray="4 2" />

                {/* Hydraulic power unit */}
                <rect x="55" y="-25" width="35" height="50" rx="3" fill="none" stroke="#f97316" strokeWidth="0.8" strokeDasharray="4 2" />

                {/* Tether connection (top rear) */}
                <circle cx="-130" cy="-50" r="5" fill="none" stroke="#64748b" strokeWidth="1" />
                <line x1="-130" y1="-55" x2="-130" y2="-80" stroke="#64748b" strokeWidth="1.5" strokeDasharray="4 3" />
                <text x="-130" y="-84" textAnchor="middle" fill="#64748b" fontSize="6" fontFamily="monospace">TO TMS</text>
              </g>

              {/* === CALLOUT LINES + LABELS === */}
              <g>
                {/* Camera array */}
                <line x1="410" y1="170" x2="470" y2="80" stroke="#3b82f6" strokeWidth="0.5" />
                <circle cx="470" cy="80" r="2" fill="#3b82f6" />
                <text x="475" y="76" fill="#3b82f6" fontSize="7" fontWeight="bold" fontFamily="monospace">HD CAMERA ARRAY</text>
                <text x="475" y="85" fill="#4a5568" fontSize="6" fontFamily="monospace">4K forward + 2x aux</text>

                {/* Lights */}
                <line x1="390" y1="132" x2="450" y2="55" stroke="#eab308" strokeWidth="0.5" />
                <circle cx="450" cy="55" r="2" fill="#eab308" />
                <text x="455" y="52" fill="#eab308" fontSize="7" fontWeight="bold" fontFamily="monospace">LED ARRAY 2x20kLm</text>
                <text x="455" y="61" fill="#4a5568" fontSize="6" fontFamily="monospace">Dimmable, 6500K</text>

                {/* Horizontal thrusters */}
                <line x1="105" y1="158" x2="45" y2="80" stroke="#f97316" strokeWidth="0.5" />
                <circle cx="45" cy="80" r="2" fill="#f97316" />
                <text x="10" y="76" fill="#f97316" fontSize="7" fontWeight="bold" fontFamily="monospace">THRUSTERS (4x HORIZ)</text>
                <text x="10" y="85" fill="#4a5568" fontSize="6" fontFamily="monospace">Tecnadyne 2060, 45kgf each</text>

                {/* Vertical thrusters */}
                <line x1="200" y1="108" x2="160" y2="55" stroke="#a78bfa" strokeWidth="0.5" />
                <circle cx="160" cy="55" r="2" fill="#a78bfa" />
                <text x="145" y="47" fill="#a78bfa" fontSize="7" fontWeight="bold" fontFamily="monospace">VERT THRUSTERS (2x)</text>
                <text x="145" y="56" fill="#4a5568" fontSize="6" fontFamily="monospace">Depth hold, 30kgf each</text>

                {/* Buoyancy */}
                <line x1="260" y1="108" x2="310" y2="40" stroke="#22c55e" strokeWidth="0.5" />
                <circle cx="310" cy="40" r="2" fill="#22c55e" />
                <text x="315" y="37" fill="#22c55e" fontSize="7" fontWeight="bold" fontFamily="monospace">BUOYANCY MODULE</text>
                <text x="315" y="46" fill="#4a5568" fontSize="6" fontFamily="monospace">Syntactic foam, rated 3000m</text>

                {/* Manipulator */}
                <line x1="130" y1="250" x2="55" y2="290" stroke="#ef4444" strokeWidth="0.5" />
                <circle cx="55" cy="290" r="2" fill="#ef4444" />
                <text x="10" y="287" fill="#ef4444" fontSize="7" fontWeight="bold" fontFamily="monospace">MANIPULATOR ARM</text>
                <text x="10" y="296" fill="#4a5568" fontSize="6" fontFamily="monospace">7-function, 100kg lift</text>

                {/* Sonar */}
                <line x1="260" y1="222" x2="310" y2="280" stroke="#a78bfa" strokeWidth="0.5" />
                <circle cx="310" cy="280" r="2" fill="#a78bfa" />
                <text x="315" y="277" fill="#a78bfa" fontSize="7" fontWeight="bold" fontFamily="monospace">MULTIBEAM SONAR</text>
                <text x="315" y="286" fill="#4a5568" fontSize="6" fontFamily="monospace">Kongsberg M3, 500kHz</text>

                {/* Battery */}
                <line x1="170" y1="190" x2="55" y2="250" stroke="#eab308" strokeWidth="0.5" />
                <circle cx="55" cy="250" r="2" fill="#eab308" />
                <text x="10" y="247" fill="#eab308" fontSize="7" fontWeight="bold" fontFamily="monospace">BATTERY PACK</text>
                <text x="10" y="256" fill="#4a5568" fontSize="6" fontFamily="monospace">Li-ion 28kWh, 240V DC</text>

                {/* Electronics */}
                <line x1="245" y1="190" x2="310" y2="250" stroke="#06b6d4" strokeWidth="0.5" />
                <circle cx="310" cy="250" r="2" fill="#06b6d4" />
                <text x="315" y="247" fill="#06b6d4" fontSize="7" fontWeight="bold" fontFamily="monospace">CONTROL ELECTRONICS</text>
                <text x="315" y="256" fill="#4a5568" fontSize="6" fontFamily="monospace">INS/DVL, fiber telemetry</text>

                {/* HPU */}
                <line x1="320" y1="190" x2="430" y2="260" stroke="#f97316" strokeWidth="0.5" />
                <circle cx="430" cy="260" r="2" fill="#f97316" />
                <text x="435" y="257" fill="#f97316" fontSize="7" fontWeight="bold" fontFamily="monospace">HYDRAULIC POWER</text>
                <text x="435" y="266" fill="#4a5568" fontSize="6" fontFamily="monospace">75HP, 207 bar</text>

                {/* Tether */}
                <line x1="130" y1="90" x2="55" y2="45" stroke="#64748b" strokeWidth="0.5" />
                <circle cx="55" cy="45" r="2" fill="#64748b" />
                <text x="10" y="42" fill="#64748b" fontSize="7" fontWeight="bold" fontFamily="monospace">UMBILICAL / TETHER</text>
                <text x="10" y="51" fill="#4a5568" fontSize="6" fontFamily="monospace">Fiber optic + power, 3000m</text>
              </g>

              {/* Dimension lines */}
              <g stroke="#4a5568" strokeWidth="0.5" opacity="0.6">
                <line x1="120" y1="305" x2="400" y2="305" />
                <line x1="120" y1="300" x2="120" y2="310" />
                <line x1="400" y1="300" x2="400" y2="310" />
                <text x="260" y="315" textAnchor="middle" fill="#4a5568" fontSize="7" fontFamily="monospace">3100mm (L)</text>

                <line x1="425" y1="125" x2="425" y2="215" />
                <line x1="420" y1="125" x2="430" y2="125" />
                <line x1="420" y1="215" x2="430" y2="215" />
                <text x="440" y="173" fill="#4a5568" fontSize="7" fontFamily="monospace" transform="rotate(90,440,173)">1800mm (H)</text>
              </g>
            </svg>
          </div>

          {/* Right: Specifications text */}
          <div style={{ padding: "12px 16px", borderLeft: "1px solid #1E2D4F" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#06b6d4", marginBottom: 4 }}>
              SUBSEA EXPLORER AUV/ROV HYBRID
            </div>
            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>
              Work-class inspection vehicle — all 5 fleet units identical
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
              <SpecSection title="DIMENSIONS &amp; DEPTH" items={[
                ["L x W x H", "3.1 x 1.9 x 1.8 m"], ["Weight", "2,800 kg (neutral)"],
                ["Max depth", "500m (1,000m D-05)"], ["Crush depth", "1,500 m"],
              ]} />
              <SpecSection title="PROPULSION &amp; POWER" items={[
                ["Thrusters", "4x horiz + 2x vert"], ["Speed", "3.5 kn, auto DP"],
                ["Battery", "Li-ion 28 kWh"], ["Endurance", "3-4 hours"],
              ]} />
              <SpecSection title="SENSORS" items={[
                ["Camera", "4K fwd + 2x HD aux"], ["Sonar", "Multibeam 500 kHz"],
                ["Nav", "INS + DVL"], ["Lights", "2x 20k lumen LED"],
              ]} />
              <SpecSection title="TOOLING" items={[
                ["Arm", "7-func, 100 kg lift"], ["NDT", "UT thickness gauge"],
                ["CP probe", "Cathodic survey"], ["Hydraulic", "75 HP, 207 bar"],
              ]} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SpecSection({ title, items }: { title: string; items: [string, string][] }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#4a5568", letterSpacing: 1, marginBottom: 2 }}>{title}</div>
      {items.map(([k, v], i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, lineHeight: 1.5 }}>
          <span style={{ color: "#94a3b8" }}>{k}</span>
          <span style={{ color: "#e2e8f0", fontWeight: 600, fontFamily: "monospace" }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

// ── Ocean Map Panel ────────────────────────────────────────
function OceanMapPanel({ drones, tick }: { drones: DroneData[]; tick: number }) {
  const MW = 1160, MH = 260;
  const latMin = 28.30, latMax = 28.52, lonMin = -89.38, lonMax = -88.95;
  const tx = (lon: number) => ((lon - lonMin) / (lonMax - lonMin)) * MW;
  const ty = (lat: number) => ((latMax - lat) / (latMax - latMin)) * MH;
  const ac: Record<string, string> = { riser: "#3b82f6", manifold: "#f97316", flowline: "#a78bfa", fpso: "#22c55e", mooring: "#eab308" };

  const connections: [string, string][] = [
    ["Riser-A","Manifold-B1"],["Riser-B","Manifold-B2"],["Riser-C","Manifold-B3"],
    ["Manifold-B1","Flowline-5"],["Manifold-B2","Flowline-12"],["Riser-C","Flowline-7"],
    ["FPSO-Hull-P1","Mooring-N1"],["FPSO-Hull-P1","Mooring-N2"],
  ];

  return (
    <div style={{ background: "#141B2D", border: "1px solid #1E2D4F", borderRadius: 8, padding: 12, marginBottom: 12 }}>
      <svg viewBox={`0 0 ${MW} ${MH}`} width="100%" style={{ display: "block", borderRadius: 6 }}>
        <defs>
          <radialGradient id="obg" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stopColor="#0c2d48" />
            <stop offset="100%" stopColor="#071525" />
          </radialGradient>
        </defs>
        <rect width={MW} height={MH} fill="url(#obg)" rx="6" />

        {/* Grid */}
        {[0.2, 0.4, 0.6, 0.8].map((p) => (
          <g key={p} opacity="0.12">
            <line x1={MW * p} y1="0" x2={MW * p} y2={MH} stroke="#1e3a5f" />
            <line x1="0" y1={MH * p} x2={MW} y2={MH * p} stroke="#1e3a5f" />
          </g>
        ))}

        <text x="8" y="18" fill="#e2e8f0" fontSize="10" fontWeight="bold" fontFamily="monospace">
          OPERATIONS MAP — Gulf Location, Block 42
        </text>
        <text x="8" y={MH - 6} fill="#1e3a5f" fontSize="7" fontFamily="monospace">
          28.30N - 28.52N | 89.38W - 88.95W
        </text>

        {/* Flowline connections */}
        {connections.map(([a, b], i) => {
          const pa = MAP_ASSETS.find((x) => x.id === a);
          const pb = MAP_ASSETS.find((x) => x.id === b);
          if (!pa || !pb) return null;
          return (
            <line key={i} x1={tx(pa.lon)} y1={ty(pa.lat)} x2={tx(pb.lon)} y2={ty(pb.lat)}
              stroke="#1e3a5f" strokeWidth="1" strokeDasharray="4 4" opacity="0.35" />
          );
        })}

        {/* Assets */}
        {MAP_ASSETS.map((a) => {
          const x = tx(a.lon), y = ty(a.lat);
          const c = ac[a.type] || "#64748b";
          return (
            <g key={a.id}>
              {a.type === "fpso" ? (
                <rect x={x - 10} y={y - 5} width="20" height="10" rx="3" fill={c} opacity="0.7" />
              ) : a.type === "flowline" ? (
                <rect x={x - 6} y={y - 2} width="12" height="4" rx="1" fill={c} opacity="0.6" />
              ) : (
                <circle cx={x} cy={y} r={a.type === "manifold" ? 6 : 5} fill={c} opacity="0.6" />
              )}
              <text x={x} y={y - 9} textAnchor="middle" fill={c} fontSize="7" fontFamily="monospace" opacity="0.85">
                {a.label}
              </text>
            </g>
          );
        })}

        {/* Drones */}
        {drones.map((d) => {
          const pos = DRONE_POSITIONS[d.drone_id];
          if (!pos) return null;
          const x = tx(pos.lon), y = ty(pos.lat);
          const sc = d.state === "idle" ? "#22c55e" : d.state === "in_mission" ? "#06b6d4"
            : d.state === "maintenance" ? "#ef4444" : "#eab308";
          const isAct = d.state === "in_mission";
          return (
            <g key={d.drone_id}>
              {isAct && (
                <circle cx={x} cy={y} r={12 + (tick % 15)} fill="none" stroke={sc}
                  strokeWidth="0.7" opacity={Math.max(0, 0.5 - (tick % 15) * 0.03)} />
              )}
              <ellipse cx={x} cy={y} rx="8" ry="4" fill={sc} opacity="0.9" />
              <circle cx={x + 5} cy={y} r="2" fill="#fff" opacity="0.5" />
              <text x={x} y={y + 12} textAnchor="middle" fill={sc} fontSize="7.5"
                fontFamily="monospace" fontWeight="bold">
                {d.drone_id.replace("DRONE-0", "D")}
              </text>
              {d.depth_m > 1 && (
                <text x={x} y={y + 20} textAnchor="middle" fill="#06b6d4" fontSize="6" fontFamily="monospace">
                  {d.depth_m.toFixed(0)}m
                </text>
              )}
            </g>
          );
        })}

        {/* Legend */}
        <g transform={`translate(${MW - 130}, 30)`}>
          <rect x="-6" y="-6" width="126" height="85" rx="4" fill="#0B0F1A" opacity="0.75" />
          {(
            [["riser", "Riser"], ["manifold", "Manifold"], ["flowline", "Flowline"],
             ["fpso", "FPSO"], ["mooring", "Mooring"]] as [string, string][]
          ).map(([t, l], i) => (
            <g key={t} transform={`translate(0,${i * 14})`}>
              <circle cx="5" cy="3" r="3.5" fill={ac[t]} opacity="0.7" />
              <text x="14" y="6.5" fill="#94a3b8" fontSize="7" fontFamily="monospace">{l}</text>
            </g>
          ))}
          <g transform="translate(0,72)">
            <ellipse cx="5" cy="0" rx="6" ry="3" fill="#06b6d4" opacity="0.9" />
            <text x="14" y="3" fill="#94a3b8" fontSize="7" fontFamily="monospace">Drone</text>
          </g>
        </g>
      </svg>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────
export default function FleetCommandPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<FleetSummary | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [missions, setMissions] = useState<any[]>([]);

  // Poll simulator every 2s, fetch DB data every 5s
  useEffect(() => {
    const fetchSim = () => {
      fetch("/api/sim/fleet").then((r) => r.json()).then(setData).catch(() => {});
    };
    const fetchDb = () => {
      fetch("/api/alerts").then((r) => { if (r.ok) return r.json(); return []; }).then(setAlerts).catch(() => {});
      fetch("/api/missions/recent").then((r) => { if (r.ok) return r.json(); return []; }).then(setMissions).catch(() => {});
    };
    fetchSim();
    fetchDb();
    const simInterval = setInterval(fetchSim, 2000);
    const dbInterval = setInterval(fetchDb, 5000);
    return () => { clearInterval(simInterval); clearInterval(dbInterval); };
  }, []);

  if (!data) return <div style={{ color: "#64748b", padding: 40 }}>Loading Fleet Command…</div>;

  const f = data.fleet;
  const env = data.environment;
  const drones = Object.values(data.drones);

  const stateColor = (s: string) =>
    s === "idle" ? "#22c55e" : s === "in_mission" ? "#06b6d4" : s === "maintenance" ? "#ef4444" : "#eab308";

  const seaStateColor = (s: string) =>
    s === "calm" ? "#22c55e" : s === "moderate" ? "#eab308" : "#ef4444";

  return (
    <div>
      {/* KPI Bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 8, marginBottom: 12 }}>
        <KPI label="OPERATIONAL" value={`${f.operational}/${f.total}`} color="#22c55e" />
        <KPI label="IN MISSION" value={`${f.in_mission}`} color="#06b6d4" />
        <KPI label="GROUNDED" value={`${f.grounded}`} color="#ef4444" />
        <KPI label="AVG HEALTH" value={`${(f.avg_health * 100).toFixed(0)}%`} color={f.avg_health > 0.8 ? "#22c55e" : "#eab308"} />
        <KPI label="AVG BATTERY" value={`${f.avg_battery.toFixed(0)}%`} color={f.avg_battery > 50 ? "#22c55e" : "#eab308"} />
        <KPI label="ANOMALIES" value={`${f.total_anomalies}`} color={f.total_anomalies > 0 ? "#ef4444" : "#22c55e"} />
        <KPI label="ALERTS" value={`${alerts.length}`} color={alerts.length > 0 ? "#f97316" : "#22c55e"} />
      </div>

      {/* Ocean Operations Map */}
      <div style={{ background: "#141B2D", border: "1px solid #1E2D4F", borderRadius: 8, padding: 12, marginBottom: 12 }}>
        <svg viewBox="0 0 1160 260" width="100%" style={{ display: "block", borderRadius: 6 }}>
          <rect width="1160" height="260" fill="#0c2d48" rx="6" />
          {[0.2,0.4,0.6,0.8].map(p=><g key={p} opacity={0.12}><line x1={1160*p} y1={0} x2={1160*p} y2={260} stroke="#1e3a5f"/><line x1={0} y1={260*p} x2={1160} y2={260*p} stroke="#1e3a5f"/></g>)}
          <text x="8" y="18" fill="#e2e8f0" fontSize="10" fontWeight="bold" fontFamily="monospace">OPERATIONS MAP — Gulf Location, Block 42</text>
          <text x="8" y="254" fill="#1e3a5f" fontSize="7" fontFamily="monospace">28.30N - 28.52N | 89.38W - 88.95W</text>

          {MAP_ASSETS.map(a => {
            const x = ((a.lon - (-89.38)) / ((-88.95) - (-89.38))) * 1160;
            const y = ((28.52 - a.lat) / (28.52 - 28.30)) * 260;
            const c = ASSET_COLORS[a.type] || "#64748b";
            return (
              <g key={a.id}>
                <circle cx={x} cy={y} r={a.type === "manifold" ? 6 : a.type === "fpso" ? 7 : 5} fill={c} opacity={0.6} />
                <text x={x} y={y - 9} textAnchor="middle" fill={c} fontSize="7" fontFamily="monospace" opacity={0.85}>{a.label}</text>
              </g>
            );
          })}

          {drones.map(d => {
            const pos = DRONE_POSITIONS[d.drone_id];
            if (!pos) return null;
            const x = ((pos.lon - (-89.38)) / ((-88.95) - (-89.38))) * 1160;
            const y = ((28.52 - pos.lat) / (28.52 - 28.30)) * 260;
            const sc = d.state === "idle" ? "#22c55e" : d.state === "in_mission" ? "#06b6d4" : d.state === "maintenance" ? "#ef4444" : "#eab308";
            return (
              <g key={d.drone_id}>
                {d.state === "in_mission" && <circle cx={x} cy={y} r={12 + (data.tick % 15)} fill="none" stroke={sc} strokeWidth={0.7} opacity={Math.max(0, 0.5 - (data.tick % 15) * 0.03)} />}
                <ellipse cx={x} cy={y} rx={8} ry={4} fill={sc} opacity={0.9} />
                <circle cx={x + 5} cy={y} r={2} fill="#fff" opacity={0.5} />
                <text x={x} y={y + 12} textAnchor="middle" fill={sc} fontSize="7.5" fontFamily="monospace" fontWeight="bold">{d.drone_id.replace("DRONE-0", "D")}</text>
                {d.depth_m > 1 && <text x={x} y={y + 20} textAnchor="middle" fill="#06b6d4" fontSize="6" fontFamily="monospace">{d.depth_m.toFixed(0)}m</text>}
              </g>
            );
          })}

          <g transform="translate(1030,30)">
            <rect x="-6" y="-6" width="126" height="85" rx="4" fill="#0B0F1A" opacity={0.75} />
            {([["riser","Riser","#3b82f6"],["manifold","Manifold","#f97316"],["flowline","Flowline","#a78bfa"],["fpso","FPSO","#22c55e"],["mooring","Mooring","#eab308"]] as [string,string,string][]).map(([t,l,c],i)=><g key={t} transform={`translate(0,${i*14})`}><circle cx={5} cy={3} r={3.5} fill={c} opacity={0.7}/><text x={14} y={6.5} fill="#94a3b8" fontSize="7" fontFamily="monospace">{l}</text></g>)}
            <g transform="translate(0,72)"><ellipse cx={5} cy={0} rx={6} ry={3} fill="#06b6d4" opacity={0.9}/><text x={14} y={3} fill="#94a3b8" fontSize="7" fontFamily="monospace">Drone</text></g>
          </g>
        </svg>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 12 }}>
        {/* Left: Fleet Grid + Missions */}
        <div>
          {/* Fleet Grid */}
          <div style={card}>
            <h3 style={sectionTitle}>Fleet Status</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginTop: 10 }}>
              {drones.map((d) => (
                <div
                  key={d.drone_id}
                  onClick={() => navigate("/fleet")}
                  style={{
                    background: "#0e1624",
                    border: `1px solid ${stateColor(d.state)}44`,
                    borderTop: `3px solid ${stateColor(d.state)}`,
                    borderRadius: 6,
                    padding: 10,
                    cursor: "pointer",
                    transition: "all 0.15s",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#e2e8f0" }}>{d.drone_id}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: stateColor(d.state), textTransform: "uppercase" }}>
                      {d.state.replace("_", " ")}
                    </span>
                  </div>

                  {/* Mini gauges */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, marginTop: 8 }}>
                    <MiniGauge label="BAT" value={d.battery_pct} max={100} color={d.battery_pct > 30 ? "#22c55e" : "#ef4444"} unit="%" />
                    <MiniGauge label="HP" value={d.health_score * 100} max={100} color={d.health_score > 0.8 ? "#22c55e" : "#eab308"} unit="%" />
                    <MiniGauge label="DEPTH" value={d.depth_m} max={500} color="#06b6d4" unit="m" />
                    <MiniGauge label="ANOM" value={d.anomaly_score * 100} max={100} color={d.anomaly_score > 0.3 ? "#ef4444" : "#22c55e"} unit="%" />
                  </div>

                  {/* Thruster bar */}
                  <div style={{ marginTop: 6 }}>
                    <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>THRUSTERS</div>
                    <div style={{ display: "flex", gap: 2 }}>
                      {d.thruster_currents.map((c, i) => (
                        <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: "#1e293b", overflow: "hidden" }}>
                          <div style={{
                            width: `${Math.min(100, (c / 5) * 100)}%`,
                            height: "100%",
                            background: c > 4 ? "#ef4444" : c > 3 ? "#eab308" : "#06b6d4",
                            borderRadius: 2,
                          }} />
                        </div>
                      ))}
                    </div>
                  </div>

                  {d.mission_id && (
                    <div style={{ fontSize: 11, color: "#a78bfa", marginTop: 4, fontWeight: 600 }}>
                      {d.mission_id}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Recent Missions */}
          <div style={{ ...card, marginTop: 12 }}>
            <h3 style={sectionTitle}>Mission History</h3>
            <table style={{ width: "100%", marginTop: 8, borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Mission", "Asset", "Type", "Status", "Start"].map((h) => (
                    <th key={h} style={{ textAlign: "left", fontSize: 12, fontWeight: 700, color: "#64748b", padding: "4px 6px", borderBottom: "1px solid #1E2D4F" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(missions || []).slice(0, 8).map((m: any, i: number) => {
                  const sc = m.status === "completed" ? "#22c55e" : m.status === "in_progress" ? "#06b6d4" : m.status === "aborted" ? "#ef4444" : "#eab308";
                  return (
                    <tr key={i} style={{ cursor: "pointer" }} onClick={() => navigate(`/inspection/${m.mission_id}`)}>
                      <td style={{ ...td, color: "#06b6d4", fontWeight: 600 }}>{m.mission_id}</td>
                      <td style={td}>{m.asset_id}</td>
                      <td style={td}>{m.asset_type}</td>
                      <td style={td}>
                        <span style={{ color: sc, fontSize: 12, fontWeight: 700, textTransform: "uppercase" }}>{m.status}</span>
                      </td>
                      <td style={{ ...td, fontSize: 12 }}>{m.start_ts?.slice(0, 16)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Vehicle Spec (below mission history) */}
          <DroneSpecPanel />
        </div>

        {/* Right: Environment + Alerts */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Environment */}
          <div style={card}>
            <h3 style={sectionTitle}>Sea Conditions</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 8 }}>
              <EnvStat label="Sea State" value={env.sea_state.toUpperCase()} color={seaStateColor(env.sea_state)} />
              <EnvStat label="Waves" value={`${env.wave_height_m}m`} color={env.wave_height_m > 2 ? "#ef4444" : "#e2e8f0"} />
              <EnvStat label="Current" value={`${env.current_speed_knots}kn`} color={env.current_speed_knots > 1.5 ? "#eab308" : "#e2e8f0"} />
              <EnvStat label="Direction" value={`${env.current_direction_deg}°`} />
              <EnvStat label="Visibility" value={`${env.visibility_m}m`} color={env.visibility_m < 5 ? "#ef4444" : "#e2e8f0"} />
              <EnvStat label="Water Temp" value={`${env.water_temp_c}°C`} />
              <EnvStat label="Weather" value={env.weather.replace("_", " ")} />
              <EnvStat label="Tick" value={`#${data.tick}`} color="#64748b" />
            </div>

            {/* Wind compass */}
            <div style={{ display: "flex", justifyContent: "center", marginTop: 10 }}>
              <svg viewBox="0 0 80 80" width="80" height="80">
                <circle cx="40" cy="40" r="35" fill="none" stroke="#1E2D4F" strokeWidth="1" />
                <circle cx="40" cy="40" r="25" fill="none" stroke="#1E2D4F" strokeWidth="0.5" strokeDasharray="2 4" />
                {["N", "E", "S", "W"].map((d, i) => {
                  const a = (i * 90 - 90) * Math.PI / 180;
                  return <text key={d} x={40 + 30 * Math.cos(a)} y={40 + 30 * Math.sin(a) + 3} textAnchor="middle" fill="#64748b" fontSize="7" fontWeight="bold">{d}</text>;
                })}
                <line
                  x1="40" y1="40"
                  x2={40 + 20 * Math.sin(env.current_direction_deg * Math.PI / 180)}
                  y2={40 - 20 * Math.cos(env.current_direction_deg * Math.PI / 180)}
                  stroke="#06b6d4" strokeWidth="2" markerEnd="url(#arrow)"
                />
                <defs>
                  <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                    <path d="M0,0 L6,3 L0,6 Z" fill="#06b6d4" />
                  </marker>
                </defs>
                <circle cx="40" cy="40" r="2" fill="#06b6d4" />
              </svg>
            </div>
          </div>

          {/* Alerts */}
          <div style={card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={sectionTitle}>Active Alerts</h3>
              {alerts.length > 0 && (
                <span style={{ fontSize: 12, fontWeight: 700, color: "#ef4444", animation: "pulse 1.5s infinite" }}>
                  {alerts.length} UNACK
                </span>
              )}
            </div>
            <div style={{ marginTop: 8, maxHeight: 280, overflowY: "auto" }}>
              {alerts.length === 0 && (
                <div style={{ color: "#22c55e", fontSize: 14, textAlign: "center", padding: 16 }}>
                  No active alerts
                </div>
              )}
              {(alerts || []).map((a: any, i: number) => {
                const sc = a.severity === "HIGH" ? "#ef4444" : a.severity === "MEDIUM" ? "#eab308" : "#64748b";
                return (
                  <div key={i} style={{
                    padding: "8px 10px",
                    borderLeft: `3px solid ${sc}`,
                    background: "#0e1624",
                    borderRadius: "0 4px 4px 0",
                    marginBottom: 4,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: sc }}>{a.severity}</span>
                      <span style={{ fontSize: 11, color: "#64748b" }}>{a.drone_id}</span>
                    </div>
                    <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 2, lineHeight: 1.4 }}>
                      {a.message}
                    </div>
                    <div style={{ fontSize: 11, color: "#4a5568", marginTop: 2 }}>
                      {a.ts?.slice(11, 19)} | {a.alert_type}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick Actions */}
          <div style={card}>
            <h3 style={sectionTitle}>Quick Actions</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
              <ActionBtn label="Plan New Mission" color="#06b6d4" onClick={() => navigate("/")} />
              <ActionBtn label="Fleet Diagnostics" color="#a78bfa" onClick={() => navigate("/fleet")} />
              <ActionBtn label="Ask Knowledge Base" color="#8b5cf6" onClick={() => navigate("/knowledge")} />
              <ActionBtn label="View Architecture" color="#22c55e" onClick={() => navigate("/dataflow")} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────

function KPI({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{
      background: "#141B2D", border: "1px solid #1E2D4F", borderRadius: 6,
      padding: "8px 10px", borderTop: `2px solid ${color}`, textAlign: "center",
    }}>
      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function MiniGauge({ label, value, max, color, unit }: { label: string; value: number; max: number; color: string; unit: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontSize: 10, color: "#4a5568", fontWeight: 700 }}>{label}</span>
        <span style={{ fontSize: 11, color, fontWeight: 700 }}>{value.toFixed(0)}{unit}</span>
      </div>
      <div style={{ height: 3, background: "#1e293b", borderRadius: 2, marginTop: 1 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

function EnvStat({ label, value, color = "#e2e8f0" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: "#0e1624", borderRadius: 4, padding: "5px 8px" }}>
      <div style={{ fontSize: 11, color: "#4a5568", fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function ActionBtn({ label, color, onClick }: { label: string; color: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      padding: "8px 12px", borderRadius: 6, border: `1px solid ${color}44`,
      background: `${color}12`, color, fontWeight: 600, fontSize: 15,
      cursor: "pointer", textAlign: "left",
    }}>
      {label}
    </button>
  );
}

// ── Styles ─────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: "#141B2D", border: "1px solid #1E2D4F", borderRadius: 8, padding: 20,
};
const sectionTitle: React.CSSProperties = {
  fontSize: 18, fontWeight: 700, color: "#e2e8f0",
};
const td: React.CSSProperties = {
  fontSize: 14, color: "#94a3b8", padding: "5px 6px", borderBottom: "1px solid #1E2D4F",
};

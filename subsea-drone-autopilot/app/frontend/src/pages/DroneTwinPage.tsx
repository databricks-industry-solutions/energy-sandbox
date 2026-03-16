import React, { useState, useEffect, useCallback } from "react";

// ── Types ──────────────────────────────────────────────────
interface Drone {
  drone_id: string;
  battery_pct: number;
  depth_m: number;
  health_score: number;
  last_heartbeat_ts: string;
  current_mission_id: string | null;
  maintenance_required: boolean;
  state: string;
  max_depth_m: number;
  max_duration_min: number;
  min_battery_reserve_pct_low_risk: number;
  min_battery_reserve_pct_med_risk: number;
  min_battery_reserve_pct_high_risk: number;
}

// Simulated live telemetry (updates each render cycle)
interface LiveTelemetry {
  depth_m: number;
  imu_roll_deg: number;
  imu_pitch_deg: number;
  imu_yaw_deg: number;
  thruster_currents: number[];
  internal_temps_c: number[];
  network_rssi_dbm: number;
  nav_error_m: number;
  battery_draw_w: number;
  propulsion_rpm: number[];
}

function simulateTelemetry(drone: Drone, tick: number): LiveTelemetry {
  const s = Math.sin;
  const c = Math.cos;
  const id = parseInt(drone.drone_id.replace("DRONE-0", ""));
  const t = tick * 0.1;

  const isActive = drone.state === "in_mission";
  const depth = isActive ? 40 + 60 * Math.abs(s(t * 0.3)) + id * 8 : drone.depth_m;

  return {
    depth_m: Math.round(depth * 10) / 10,
    imu_roll_deg: Math.round((s(t * 1.2 + id) * 4 + (isActive ? s(t * 3) * 2 : 0)) * 10) / 10,
    imu_pitch_deg: Math.round((c(t * 0.8 + id) * 3 + (isActive ? c(t * 2.5) * 1.5 : 0)) * 10) / 10,
    imu_yaw_deg: Math.round((180 + s(t * 0.2) * 30) * 10) / 10,
    thruster_currents: [0, 1, 2, 3].map(
      (i) => Math.round((isActive ? 2.5 + s(t + i) * 1.2 : 0.1) * 100) / 100
    ),
    internal_temps_c: [0, 1, 2].map(
      (i) => Math.round((28 + id * 2 + s(t * 0.5 + i) * 3 + (isActive ? 8 : 0)) * 10) / 10
    ),
    network_rssi_dbm: Math.round(-45 - Math.abs(s(t * 0.4)) * 25 - (isActive ? depth * 0.05 : 0)),
    nav_error_m: Math.round((0.2 + Math.abs(s(t * 1.5)) * 0.8 + (isActive ? 0.3 : 0)) * 100) / 100,
    battery_draw_w: Math.round((isActive ? 120 + s(t * 2) * 30 : 5) * 10) / 10,
    propulsion_rpm: [0, 1, 2, 3].map(
      (i) => Math.round(isActive ? 1200 + s(t * 2 + i) * 300 : 0)
    ),
  };
}

// ── SVG Drone Digital Twin ─────────────────────────────────
function DroneTwinSVG({
  drone,
  telemetry,
  tick,
}: {
  drone: Drone;
  telemetry: LiveTelemetry;
  tick: number;
}) {
  const isActive = drone.state === "in_mission";
  const roll = telemetry.imu_roll_deg;
  const pitch = telemetry.imu_pitch_deg;

  // Depth scale — centered on drone's actual depth, range adapts
  const currentDepth = telemetry.depth_m;
  const isSubmerged = currentDepth > 2;

  let scaleMin: number, scaleMax: number;
  if (!isSubmerged) {
    // At surface: show 0–1m (drone is docked/resting)
    scaleMin = 0;
    scaleMax = 1;
  } else if (currentDepth < 30) {
    // Shallow: 0 to depth*2+20
    scaleMin = 0;
    scaleMax = Math.round(currentDepth * 2 + 20);
  } else {
    // Deep: bracket around current depth
    const halfRange = Math.max(40, currentDepth * 0.5);
    scaleMin = Math.max(0, Math.round(currentDepth - halfRange));
    scaleMax = Math.round(currentDepth + halfRange);
  }

  // 4 evenly spaced depth labels across the range
  const depthLabels = Array.from({ length: 4 }, (_, i) =>
    Math.round(scaleMin + ((scaleMax - scaleMin) * (i + 1)) / 5)
  );

  // Status color
  const stateColor =
    drone.state === "idle"
      ? "#22c55e"
      : drone.state === "in_mission"
      ? "#06b6d4"
      : drone.state === "maintenance"
      ? "#ef4444"
      : "#eab308";

  // Thruster animation
  const thrusterSpin = tick * 15;

  return (
    <svg viewBox="0 0 400 320" width="100%" style={{ display: "block" }}>
      {/* Background: water gradient */}
      <defs>
        <linearGradient id="water-bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0a1929" />
          <stop offset="60%" stopColor="#071525" />
          <stop offset="100%" stopColor="#030d1a" />
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="45%" r="40%">
          <stop offset="0%" stopColor={stateColor} stopOpacity="0.08" />
          <stop offset="100%" stopColor={stateColor} stopOpacity="0" />
        </radialGradient>
        <filter id="drone-shadow">
          <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor={stateColor} floodOpacity="0.3" />
        </filter>
      </defs>

      <rect width="400" height="320" fill="url(#water-bg)" rx="8" />
      <rect width="400" height="320" fill="url(#glow)" rx="8" />

      {/* Depth grid lines — only show when submerged */}
      {isSubmerged && depthLabels.map((d, i) => {
        const y = 60 + i * 55;
        return (
          <g key={i}>
            <line x1="0" y1={y} x2="400" y2={y} stroke="#1e3a5f" strokeWidth="0.5" strokeDasharray="4 8" />
            <text x="4" y={y - 3} fill="#1e3a5f" fontSize="8" fontFamily="monospace">{d}m</text>
          </g>
        );
      })}

      {/* Current depth label at drone center */}
      <text x="4" y="153" fill="#06b6d4" fontSize="9" fontFamily="monospace" fontWeight="bold">
        {isSubmerged ? `${currentDepth}m` : "0m SURFACE"}
      </text>
      {isSubmerged && <line x1="35" y1="150" x2="145" y2="150" stroke="#06b6d4" strokeWidth="1" strokeDasharray="3 3" opacity="0.4" />}

      {/* ROV/AUV body group — always centered */}
      <g
        transform={`translate(200, 150) rotate(${roll * 0.5})`}
        filter="url(#drone-shadow)"
      >
        {/* Tether cable (top) */}
        <path
          d={`M0,-28 C-5,-45 5,-60 0,-80 C-3,-90 3,-95 0,-100`}
          stroke="#4a5568" strokeWidth="1.5" fill="none" strokeDasharray="4 3" opacity="0.5"
        />
        <circle cx="0" cy="-28" r="2" fill="#4a5568" />

        {/* Main hull — torpedo shape */}
        <rect x="-65" y="-18" width="130" height="36" rx="18" fill="#2a3444" stroke="#4a5568" strokeWidth="1.5" />
        {/* Hull top highlight */}
        <rect x="-60" y="-16" width="120" height="14" rx="14" fill="#3a4555" opacity="0.6" />
        {/* Hull panel lines */}
        <line x1="-30" y1="-18" x2="-30" y2="18" stroke="#4a5568" strokeWidth="0.5" opacity="0.4" />
        <line x1="30" y1="-18" x2="30" y2="18" stroke="#4a5568" strokeWidth="0.5" opacity="0.4" />

        {/* Forward camera array (nose) */}
        <circle cx="58" cy="0" r="7" fill="#1a2535" stroke="#06b6d4" strokeWidth="1" />
        <circle cx="58" cy="0" r="3.5" fill={isActive ? "#06b6d4" : "#1e3a5f"} opacity={isActive ? 0.8 : 0.3}>
          {isActive && <animate attributeName="opacity" values="0.4;0.9;0.4" dur="2s" repeatCount="indefinite" />}
        </circle>
        {/* Secondary cameras */}
        <circle cx="50" cy="-12" r="3" fill="#1a2535" stroke="#3b82f6" strokeWidth="0.7" />
        <circle cx="50" cy="12" r="3" fill="#1a2535" stroke="#3b82f6" strokeWidth="0.7" />

        {/* Forward lights */}
        <ellipse cx="45" cy="-15" rx="4" ry="2" fill={isActive ? "#fbbf24" : "#4a5568"} opacity={isActive ? 0.7 : 0.2}>
          {isActive && <animate attributeName="opacity" values="0.5;0.8;0.5" dur="3s" repeatCount="indefinite" />}
        </ellipse>
        <ellipse cx="45" cy="15" rx="4" ry="2" fill={isActive ? "#fbbf24" : "#4a5568"} opacity={isActive ? 0.7 : 0.2}>
          {isActive && <animate attributeName="opacity" values="0.5;0.8;0.5" dur="3s" repeatCount="indefinite" />}
        </ellipse>

        {/* Lateral thrusters (4 ducted) */}
        {([
          [-55, -22],   // port top
          [-55, 22],    // port bottom
          [55, -22],    // starboard top
          [55, 22],     // starboard bottom
        ] as [number, number][]).map(([tx, ty], i) => (
          <g key={i} transform={`translate(${tx}, ${ty})`}>
            {/* Thruster duct */}
            <ellipse cx="0" cy="0" rx="8" ry="5" fill="#1e293b" stroke="#4a5568" strokeWidth="1" />
            {/* Propeller blades */}
            <g transform={`rotate(${isActive ? thrusterSpin + i * 45 : 0})`}>
              <ellipse cx="0" cy="0" rx="6" ry="1.5" fill={isActive ? "#06b6d4" : "#374151"} opacity={isActive ? 0.6 : 0.3} />
              <ellipse cx="0" cy="0" rx="1.5" ry="6" fill={isActive ? "#06b6d4" : "#374151"} opacity={isActive ? 0.6 : 0.3} />
            </g>
            <circle cx="0" cy="0" r="1.5" fill="#4a5568" />
            {/* Current readout */}
            <text x="0" y={ty < 0 ? -9 : 12} textAnchor="middle" fill="#64748b" fontSize="6" fontFamily="monospace">
              {telemetry.thruster_currents[i]}A
            </text>
          </g>
        ))}

        {/* Vertical thrusters (top, for depth control) */}
        {[-20, 20].map((vx, i) => (
          <g key={`vt-${i}`} transform={`translate(${vx}, -22)`}>
            <rect x="-5" y="-4" width="10" height="8" rx="2" fill="#1e293b" stroke="#4a5568" strokeWidth="0.8" />
            <line x1="-3" y1="0" x2="3" y2="0" stroke={isActive ? "#06b6d4" : "#374151"} strokeWidth="1.5"
              opacity={isActive ? 0.6 : 0.3}
              transform={`rotate(${isActive ? thrusterSpin * 2 : 0})`} />
          </g>
        ))}

        {/* Manipulator arm (port side, folded) */}
        <g transform="translate(-50, 12)">
          <line x1="0" y1="0" x2="-15" y2="10" stroke="#f97316" strokeWidth="2" strokeLinecap="round" />
          <line x1="-15" y1="10" x2="-8" y2="18" stroke="#f97316" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="-8" cy="18" r="2" fill="#f97316" stroke="#ea580c" strokeWidth="0.5" />
          <line x1="-9.5" y1="17" x2="-6.5" y2="19" stroke="#ea580c" strokeWidth="1" />
        </g>

        {/* Sonar dome (belly) */}
        <ellipse cx="0" cy="16" rx="12" ry="4" fill="#1e293b" stroke="#a78bfa" strokeWidth="0.7" opacity="0.6" />

        {/* Status lights (top) */}
        <circle cx="-40" cy="-16" r="2" fill={stateColor}>
          <animate attributeName="opacity" values="1;0.3;1" dur="1.5s" repeatCount="indefinite" />
        </circle>
        <circle cx="-35" cy="-16" r="2" fill="#22c55e" opacity="0.5" />

        {/* Drone ID plate */}
        <rect x="-28" y="-7" width="56" height="14" rx="3" fill="#0B0F1A" opacity="0.7" />
        <text x="0" y="2" textAnchor="middle" fill="#e2e8f0" fontSize="9" fontWeight="bold" fontFamily="monospace">
          {drone.drone_id}
        </text>

        {/* Rear propulsion nozzle */}
        <ellipse cx="-65" cy="0" rx="4" ry="10" fill="#1e293b" stroke="#4a5568" strokeWidth="1" />
        {isActive && (
          <g opacity="0.4">
            {[0, 1, 2].map((j) => (
              <circle key={j} cx={-72 - j * 4 - (tick % 3)} cy={Math.sin(tick * 0.5 + j) * 3} r={1.5 - j * 0.3}
                fill="#06b6d4" opacity={0.3 - j * 0.08} />
            ))}
          </g>
        )}
      </g>

      {/* Bubble particles (thruster wash when active) */}
      {isActive &&
        [0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
          const bx = 140 + (i % 4) * 30 + Math.sin(tick * 0.3 + i) * 6;
          const by = 175 - ((tick * 1.5 + i * 15) % 80);
          return (
            <circle key={i} cx={bx} cy={by} r={0.8 + (i % 3) * 0.4}
              fill="#06b6d4" opacity={0.1 + (i % 4) * 0.05} />
          );
        })}

      {/* Telemetry HUD overlay */}
      <g>
        {/* Battery */}
        <rect x="310" y="10" width="80" height="50" rx="4" fill="#0B0F1A" opacity="0.8" />
        <text x="320" y="24" fill="#64748b" fontSize="8" fontFamily="monospace">BATTERY</text>
        <text x="320" y="40" fill={drone.battery_pct > 30 ? "#22c55e" : "#ef4444"} fontSize="16" fontWeight="bold" fontFamily="monospace">
          {drone.battery_pct}%
        </text>
        <rect x="320" y="46" width="60" height="4" rx="1" fill="#1e293b" />
        <rect x="320" y="46" width={drone.battery_pct * 0.6} height="4" rx="1" fill={drone.battery_pct > 30 ? "#22c55e" : "#ef4444"} />

        {/* Depth */}
        <rect x="310" y="66" width="80" height="40" rx="4" fill="#0B0F1A" opacity="0.8" />
        <text x="320" y="80" fill="#64748b" fontSize="8" fontFamily="monospace">DEPTH</text>
        <text x="320" y="96" fill="#06b6d4" fontSize="14" fontWeight="bold" fontFamily="monospace">
          {telemetry.depth_m}m
        </text>

        {/* IMU */}
        <rect x="310" y="112" width="80" height="50" rx="4" fill="#0B0F1A" opacity="0.8" />
        <text x="320" y="126" fill="#64748b" fontSize="8" fontFamily="monospace">IMU</text>
        <text x="320" y="138" fill="#e2e8f0" fontSize="9" fontFamily="monospace">
          R:{roll.toFixed(1)}
        </text>
        <text x="320" y="150" fill="#e2e8f0" fontSize="9" fontFamily="monospace">
          P:{pitch.toFixed(1)}
        </text>

        {/* RSSI */}
        <rect x="310" y="168" width="80" height="40" rx="4" fill="#0B0F1A" opacity="0.8" />
        <text x="320" y="182" fill="#64748b" fontSize="8" fontFamily="monospace">COMMS</text>
        <text
          x="320"
          y="198"
          fill={telemetry.network_rssi_dbm > -60 ? "#22c55e" : telemetry.network_rssi_dbm > -75 ? "#eab308" : "#ef4444"}
          fontSize="12"
          fontWeight="bold"
          fontFamily="monospace"
        >
          {telemetry.network_rssi_dbm}dBm
        </text>

        {/* Nav Error */}
        <rect x="10" y="260" width="380" height="50" rx="4" fill="#0B0F1A" opacity="0.7" />
        <text x="20" y="276" fill="#64748b" fontSize="8" fontFamily="monospace">
          NAV ERR: {telemetry.nav_error_m}m | DRAW: {telemetry.battery_draw_w}W | TEMPS: {telemetry.internal_temps_c.join("/")}°C
        </text>
        <text x="20" y="296" fill="#64748b" fontSize="8" fontFamily="monospace">
          RPM: {telemetry.propulsion_rpm.join(" / ")} | STATE: {drone.state.toUpperCase()} | HEALTH: {drone.health_score.toFixed(2)}
        </text>
      </g>
    </svg>
  );
}

// ── Gauge Component ────────────────────────────────────────
function Gauge({
  label,
  value,
  min,
  max,
  unit = "",
  thresholds,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  unit?: string;
  thresholds: { green: number; amber: number };
}) {
  const pct = Math.min(1, Math.max(0, (value - min) / (max - min)));
  const angle = -135 + pct * 270;
  const color =
    value <= thresholds.green
      ? "#22c55e"
      : value <= thresholds.amber
      ? "#eab308"
      : "#ef4444";

  // Arc geometry: 270° arc from 135° to 405° (or -225° to 45°)
  const r = 32;
  const cx = 50;
  const cy = 46;
  const startAngle = 135; // bottom-left
  const endAngle = 405;   // bottom-right (135 + 270)
  const arcLen = r * (270 * Math.PI / 180); // ≈ 150.8

  // Needle position: map pct to angle along the arc
  const needleAngleDeg = startAngle + pct * 270;
  const needleRad = (needleAngleDeg * Math.PI) / 180;
  const needleLen = r * 0.75;
  const nx = cx + needleLen * Math.cos(needleRad);
  const ny = cy + needleLen * Math.sin(needleRad);

  // Arc endpoints
  const sx = cx + r * Math.cos((startAngle * Math.PI) / 180);
  const sy = cy + r * Math.sin((startAngle * Math.PI) / 180);
  const ex = cx + r * Math.cos((endAngle * Math.PI) / 180);
  const ey = cy + r * Math.sin((endAngle * Math.PI) / 180);

  const arcPath = `M ${sx.toFixed(1)} ${sy.toFixed(1)} A ${r} ${r} 0 1 1 ${ex.toFixed(1)} ${ey.toFixed(1)}`;

  return (
    <div style={{ textAlign: "center" }}>
      <svg viewBox="0 0 100 70" width="100%" style={{ maxWidth: 120 }}>
        {/* Arc track */}
        <path d={arcPath} fill="none" stroke="#1e293b" strokeWidth="5" strokeLinecap="round" />
        {/* Value arc */}
        <path
          d={arcPath}
          fill="none"
          stroke={color}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${pct * arcLen} ${arcLen}`}
          opacity="0.85"
        />
        {/* Tick marks */}
        {[0, 0.25, 0.5, 0.75, 1].map((p, i) => {
          const a = ((startAngle + p * 270) * Math.PI) / 180;
          const inner = r - 4;
          const outer = r + 2;
          return (
            <line key={i}
              x1={cx + inner * Math.cos(a)} y1={cy + inner * Math.sin(a)}
              x2={cx + outer * Math.cos(a)} y2={cy + outer * Math.sin(a)}
              stroke="#4a5568" strokeWidth="1"
            />
          );
        })}
        {/* Needle */}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={color} strokeWidth="2" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="3" fill={color} />
        <circle cx={cx} cy={cy} r="1.5" fill="#0B0F1A" />
        {/* Value text */}
        <text x={cx} y="64" textAnchor="middle" fill="#e2e8f0" fontSize="10" fontWeight="bold">
          {typeof value === "number" ? value.toFixed(1) : value}
          {unit}
        </text>
      </svg>
      <div style={{ fontSize: 9, color: "#64748b", fontWeight: 600, marginTop: -4 }}>{label}</div>
    </div>
  );
}

// ── Fleet Card ─────────────────────────────────────────────
function DroneCard({
  drone,
  selected,
  onClick,
}: {
  drone: Drone;
  selected: boolean;
  onClick: () => void;
}) {
  const stateColor =
    drone.state === "idle"
      ? "#22c55e"
      : drone.state === "in_mission"
      ? "#06b6d4"
      : drone.state === "maintenance"
      ? "#ef4444"
      : "#eab308";

  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? "#141B2D" : "#0e1624",
        border: `2px solid ${selected ? "#06b6d4" : "#1E2D4F"}`,
        borderRadius: 8,
        padding: 12,
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: "#e2e8f0" }}>{drone.drone_id}</span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            padding: "3px 8px",
            borderRadius: 3,
            background: stateColor + "22",
            color: stateColor,
            border: `1px solid ${stateColor}44`,
            textTransform: "uppercase",
          }}
        >
          {drone.state}
        </span>
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
        <MiniStat label="Battery" value={`${drone.battery_pct}%`} color={drone.battery_pct > 30 ? "#22c55e" : "#ef4444"} />
        <MiniStat label="Health" value={drone.health_score.toFixed(2)} color={drone.health_score > 0.8 ? "#22c55e" : "#eab308"} />
        <MiniStat label="Max Depth" value={`${drone.max_depth_m}m`} />
      </div>
      {drone.maintenance_required && (
        <div style={{ fontSize: 10, color: "#ef4444", fontWeight: 600, marginTop: 6 }}>
          MAINTENANCE REQUIRED
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, color = "#e2e8f0" }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: "#64748b" }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────
export default function DroneTwinPage() {
  const [drones, setDrones] = useState<Drone[]>([]);
  const [selectedId, setSelectedId] = useState<string>("DRONE-01");
  const [tick, setTick] = useState(0);
  const [telemetryHistory, setTelemetryHistory] = useState<LiveTelemetry[]>([]);

  // Fetch fleet data from simulator (always available, no DB dependency)
  useEffect(() => {
    fetch("/api/sim/fleet")
      .then((r) => r.json())
      .then((data) => {
        const droneList: Drone[] = Object.values(data.drones || {}).map((d: any) => ({
          drone_id: d.drone_id,
          battery_pct: d.battery_pct,
          depth_m: d.depth_m,
          health_score: d.health_score,
          last_heartbeat_ts: "",
          current_mission_id: d.mission_id,
          maintenance_required: d.state === "maintenance",
          state: d.state,
          max_depth_m: d.drone_id === "DRONE-05" ? 1000 : d.drone_id === "DRONE-03" ? 300 : 500,
          max_duration_min: d.drone_id === "DRONE-05" ? 240 : d.drone_id === "DRONE-03" ? 120 : 180,
          min_battery_reserve_pct_low_risk: 30,
          min_battery_reserve_pct_med_risk: 40,
          min_battery_reserve_pct_high_risk: 50,
        }));
        setDrones(droneList);
        if (droneList.length > 0 && !droneList.find((d) => d.drone_id === selectedId)) {
          setSelectedId(droneList[0].drone_id);
        }
      })
      .catch(() => {});
  }, []);

  // Animation tick (updates every 500ms for live telemetry)
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 500);
    return () => clearInterval(interval);
  }, []);

  const selected = drones.find((d) => d.drone_id === selectedId) || drones[0];
  const telemetry = selected ? simulateTelemetry(selected, tick) : null;

  // Keep telemetry history for trend (last 40 ticks)
  useEffect(() => {
    if (telemetry) {
      setTelemetryHistory((prev) => [...prev.slice(-39), telemetry]);
    }
  }, [tick, selectedId]);

  if (!selected || !telemetry) return <div style={{ color: "#64748b" }}>Loading fleet…</div>;

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>
        Drone Digital Twin
      </h2>

      {/* Fleet selector */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          gap: 8,
          marginBottom: 12,
        }}
      >
        {drones.map((d) => (
          <DroneCard
            key={d.drone_id}
            drone={d}
            selected={d.drone_id === selectedId}
            onClick={() => {
              setSelectedId(d.drone_id);
              setTelemetryHistory([]);
            }}
          />
        ))}
      </div>

      {/* Twin + Gauges */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 14 }}>
        {/* Digital Twin SVG */}
        <div style={card}>
          <DroneTwinSVG drone={selected} telemetry={telemetry} tick={tick} />
        </div>

        {/* Gauges panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={card}>
            <h3 style={sectionTitle}>Diagnostics</h3>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 8,
                marginTop: 8,
              }}
            >
              <Gauge label="Battery" value={selected.battery_pct} min={0} max={100} unit="%" thresholds={{ green: 50, amber: 30 }} />
              <Gauge label="Health" value={selected.health_score * 100} min={0} max={100} unit="" thresholds={{ green: 80, amber: 60 }} />
              <Gauge label="Depth" value={telemetry.depth_m} min={0} max={selected.max_depth_m} unit="m" thresholds={{ green: selected.max_depth_m * 0.6, amber: selected.max_depth_m * 0.85 }} />
              <Gauge label="Nav Error" value={telemetry.nav_error_m} min={0} max={5} unit="m" thresholds={{ green: 1, amber: 2.5 }} />
              <Gauge label="RSSI" value={Math.abs(telemetry.network_rssi_dbm)} min={0} max={100} unit="" thresholds={{ green: 55, amber: 75 }} />
              <Gauge
                label="Max Temp"
                value={Math.max(...telemetry.internal_temps_c)}
                min={20}
                max={65}
                unit="°C"
                thresholds={{ green: 40, amber: 50 }}
              />
            </div>
          </div>

          {/* Limits card */}
          <div style={card}>
            <h3 style={sectionTitle}>Safety Envelope</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 8 }}>
              <LimitRow label="Max Depth" value={`${selected.max_depth_m}m`} />
              <LimitRow label="Max Duration" value={`${selected.max_duration_min}min`} />
              <LimitRow label="Low Risk Reserve" value={`${selected.min_battery_reserve_pct_low_risk}%`} />
              <LimitRow label="Med Risk Reserve" value={`${selected.min_battery_reserve_pct_med_risk}%`} />
              <LimitRow label="High Risk Reserve" value={`${selected.min_battery_reserve_pct_high_risk}%`} />
              <LimitRow label="Maintenance" value={selected.maintenance_required ? "REQUIRED" : "OK"} color={selected.maintenance_required ? "#ef4444" : "#22c55e"} />
            </div>
          </div>
        </div>
      </div>

      {/* Telemetry trend (sparklines) */}
      <div style={{ ...card, marginTop: 12 }}>
        <h3 style={sectionTitle}>Live Telemetry Trend</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 8 }}>
          <Sparkline
            label="Depth (m)"
            data={telemetryHistory.map((t) => t.depth_m)}
            color="#06b6d4"
            max={selected.max_depth_m}
          />
          <Sparkline
            label="Nav Error (m)"
            data={telemetryHistory.map((t) => t.nav_error_m)}
            color="#eab308"
            max={5}
          />
          <Sparkline
            label="Max Thruster (A)"
            data={telemetryHistory.map((t) => Math.max(...t.thruster_currents))}
            color="#a78bfa"
            max={6}
          />
          <Sparkline
            label="Max Temp (°C)"
            data={telemetryHistory.map((t) => Math.max(...t.internal_temps_c))}
            color="#f97316"
            max={65}
          />
        </div>
      </div>
    </div>
  );
}

// ── Sparkline ──────────────────────────────────────────────
function Sparkline({
  label,
  data,
  color,
  max,
}: {
  label: string;
  data: number[];
  color: string;
  max: number;
}) {
  const w = 200;
  const h = 40;
  if (data.length < 2) return <div style={{ height: h + 20 }} />;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - (v / max) * h;
    return `${x},${y}`;
  });

  const current = data[data.length - 1];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 13, color: "#64748b", fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color }}>{current.toFixed(1)}</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ marginTop: 4 }}>
        <polyline points={points.join(" ")} fill="none" stroke={color} strokeWidth="1.5" opacity="0.8" />
        {/* Last point dot */}
        {data.length > 0 && (
          <circle
            cx={(data.length - 1) / (data.length - 1) * w}
            cy={h - (current / max) * h}
            r="2.5"
            fill={color}
          />
        )}
      </svg>
    </div>
  );
}

function LimitRow({ label, value, color = "#e2e8f0" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: "#0B0F1A", borderRadius: 4, padding: "6px 10px" }}>
      <div style={{ fontSize: 12, color: "#64748b" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color }}>{value}</div>
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
const sectionTitle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 700,
  color: "#e2e8f0",
};

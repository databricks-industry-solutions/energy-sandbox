import React, { useState, useRef, useEffect } from "react";
import { useParams } from "react-router-dom";

// ── Types ──────────────────────────────────────────────────
interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface ModelOutput {
  defect_type: string;
  confidence: number;
  bbox: BBox | null;
  color: string;
}

interface FrameVisual {
  visibility_m: number;
  water_color: string;
  particulate: number;
  light_angle: number;
}

interface Frame {
  frame_id: string;
  index: number;
  ts: string;
  depth_m: number;
  image_path: string;
  severity_score: number;
  defect_type: string;
  asset_part: string;
  model_output: ModelOutput;
  camera_pose: { roll: number; pitch: number; yaw: number };
  visual: FrameVisual;
}

interface FrameEvent {
  frame: Frame;
  analysis: string;
  progress: number;
  frames_processed: number;
  total_frames: number;
  running_defect_counts: Record<string, number>;
  high_severity_count: number;
}

// ── Synthetic Underwater Frame Renderer (SVG) ──────────────
function UnderwaterFrame({
  frame,
  size = 320,
  showAnnotation = true,
}: {
  frame: Frame;
  size?: number;
  showAnnotation?: boolean;
}) {
  const v = frame.visual;
  const mo = frame.model_output;
  const hasDefect = mo.defect_type !== "no_issue" && mo.bbox;
  const seed = frame.frame_id.charCodeAt(frame.frame_id.length - 1);

  // Generate pseudo-random particles
  const particles = Array.from({ length: Math.floor(v.particulate * 30) }, (_, i) => ({
    cx: ((seed * 7 + i * 31) % 100),
    cy: ((seed * 13 + i * 17) % 100),
    r: 0.3 + (i % 3) * 0.3,
    opacity: 0.15 + (i % 5) * 0.08,
  }));

  // Generate structure elements (pipes, surfaces)
  const structureY = 40 + (seed % 25);

  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      style={{ borderRadius: 6, display: "block" }}
    >
      {/* Water background gradient */}
      <defs>
        <radialGradient id={`light-${frame.frame_id}`} cx={`${v.light_angle / 1.6}%`} cy="20%" r="60%">
          <stop offset="0%" stopColor={v.water_color} stopOpacity="0.5" />
          <stop offset="100%" stopColor="#031525" stopOpacity="1" />
        </radialGradient>
        <filter id={`blur-${frame.frame_id}`}>
          <feGaussianBlur stdDeviation={Math.max(0, (15 - v.visibility_m) * 0.15)} />
        </filter>
      </defs>

      <rect width="100" height="100" fill={`url(#light-${frame.frame_id})`} />

      {/* Underwater structure (pipe/plate surface) */}
      <g filter={`url(#blur-${frame.frame_id})`}>
        <rect x="5" y={structureY} width="90" height="35" rx="2" fill="#3a3f4a" opacity="0.7" />
        <rect x="5" y={structureY} width="90" height="1.5" fill="#5a6070" opacity="0.5" />
        <rect x="5" y={structureY + 12} width="90" height="0.8" fill="#4a5060" opacity="0.3" />
        {/* Weld line */}
        <path
          d={`M8,${structureY + 20} Q30,${structureY + 18} 50,${structureY + 21} T92,${structureY + 19}`}
          stroke="#6a7080" strokeWidth="1.2" fill="none" opacity="0.4"
        />
      </g>

      {/* Marine growth spots */}
      {frame.defect_type === "marine_growth" && (
        <g opacity="0.6">
          {[0, 1, 2, 3, 4].map((i) => (
            <circle
              key={i}
              cx={15 + i * 18}
              cy={structureY + 8 + (i % 2) * 12}
              r={2 + (i % 3)}
              fill="#166534"
              opacity={0.4 + (i % 3) * 0.15}
            />
          ))}
        </g>
      )}

      {/* Corrosion texture */}
      {frame.defect_type === "corrosion" && mo.bbox && (
        <g>
          <rect
            x={mo.bbox.x} y={mo.bbox.y + structureY - 30}
            width={mo.bbox.w} height={mo.bbox.h}
            fill="#92400e" opacity="0.5" rx="1"
          />
          {[0, 1, 2].map((i) => (
            <circle
              key={i}
              cx={mo.bbox!.x + 5 + i * 10}
              cy={mo.bbox!.y + structureY - 25 + (i % 2) * 8}
              r={1.5 + i * 0.5}
              fill="#dc2626" opacity="0.4"
            />
          ))}
        </g>
      )}

      {/* Crack indication */}
      {frame.defect_type === "crack" && mo.bbox && (
        <path
          d={`M${mo.bbox.x},${mo.bbox.y + structureY - 25} l${mo.bbox.w * 0.4},${mo.bbox.h * 0.3} l${mo.bbox.w * 0.3},-${mo.bbox.h * 0.1} l${mo.bbox.w * 0.3},${mo.bbox.h * 0.2}`}
          stroke="#fca5a5" strokeWidth="0.8" fill="none" opacity="0.7"
        />
      )}

      {/* Floating particles */}
      {particles.map((p, i) => (
        <circle key={i} cx={p.cx} cy={p.cy} r={p.r} fill="#94a3b8" opacity={p.opacity} />
      ))}

      {/* ML Bounding box annotation */}
      {showAnnotation && hasDefect && mo.bbox && (
        <g>
          <rect
            x={mo.bbox.x}
            y={mo.bbox.y}
            width={mo.bbox.w}
            height={mo.bbox.h}
            fill="none"
            stroke={mo.color}
            strokeWidth="1.2"
            strokeDasharray="3 2"
            opacity="0.9"
          />
          <rect
            x={mo.bbox.x}
            y={mo.bbox.y - 7}
            width={mo.bbox.w + 10}
            height="7"
            fill={mo.color}
            opacity="0.85"
            rx="1"
          />
          <text
            x={mo.bbox.x + 1.5}
            y={mo.bbox.y - 1.5}
            fill="white"
            fontSize="4"
            fontWeight="bold"
            fontFamily="monospace"
          >
            {mo.defect_type} {(mo.confidence * 100).toFixed(0)}%
          </text>
        </g>
      )}

      {/* Depth overlay */}
      <rect x="2" y="2" width="22" height="8" rx="1.5" fill="#000" opacity="0.6" />
      <text x="4" y="8" fill="#06b6d4" fontSize="4.5" fontWeight="bold" fontFamily="monospace">
        {frame.depth_m}m
      </text>

      {/* Frame ID */}
      <rect x="65" y="2" width="33" height="8" rx="1.5" fill="#000" opacity="0.6" />
      <text x="67" y="8" fill="#94a3b8" fontSize="3.5" fontFamily="monospace">
        {frame.frame_id.slice(-7)}
      </text>

      {/* Severity indicator bar */}
      <rect x="2" y="93" width="96" height="5" rx="1" fill="#1e293b" opacity="0.7" />
      <rect
        x="2"
        y="93"
        width={Math.max(2, frame.severity_score * 96)}
        height="5"
        rx="1"
        fill={
          frame.severity_score > 0.6
            ? "#ef4444"
            : frame.severity_score > 0.3
            ? "#eab308"
            : "#22c55e"
        }
        opacity="0.8"
      />
    </svg>
  );
}

// ── Defect Count Badge ─────────────────────────────────────
function DefectBadge({ type, count }: { type: string; count: number }) {
  const colors: Record<string, string> = {
    corrosion: "#ef4444",
    coating_damage: "#f97316",
    marine_growth: "#22c55e",
    anode_depletion: "#eab308",
    crack: "#dc2626",
  };
  const c = colors[type] || "#64748b";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "3px 8px",
        borderRadius: 4,
        fontSize: 13,
        fontWeight: 700,
        background: c + "18",
        color: c,
        border: `1px solid ${c}44`,
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: c,
          display: "inline-block",
        }}
      />
      {type.replace("_", " ")} ({count})
    </span>
  );
}

// ── Main Page Component ────────────────────────────────────
export default function LiveInspectionPage() {
  const { missionId: routeMissionId } = useParams<{ missionId: string }>();
  const [missionId, setMissionId] = useState(routeMissionId || "MIS-DEMO-001");
  const [frames, setFrames] = useState<Frame[]>([]);
  const [analyses, setAnalyses] = useState<Map<string, string>>(new Map());
  const [selectedFrame, setSelectedFrame] = useState<Frame | null>(null);
  const [progress, setProgress] = useState(0);
  const [running, setRunning] = useState(false);
  const [defectCounts, setDefectCounts] = useState<Record<string, number>>({});
  const [highSevCount, setHighSevCount] = useState(0);
  const [completeSummary, setCompleteSummary] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const filmstripRef = useRef<HTMLDivElement>(null);

  const startLiveAnalysis = async () => {
    setRunning(true);
    setFrames([]);
    setAnalyses(new Map());
    setSelectedFrame(null);
    setProgress(0);
    setDefectCounts({});
    setHighSevCount(0);
    setCompleteSummary("");
    setLogs([]);

    const resp = await fetch("/api/inspection/live-analysis/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mission_id: missionId, auto_analyze: true }),
    });

    const reader = resp.body!.getReader();
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
          let data: any;
          try { data = JSON.parse(line.slice(5).trim()); } catch { continue; }

          if (currentEvent === "status") {
            setLogs((prev) => [...prev, data.message || "Processing..."]);
          } else if (currentEvent === "frame") {
            const fe = data as FrameEvent;
            setFrames((prev) => [...prev, fe.frame]);
            setAnalyses((prev) => new Map(prev).set(fe.frame.frame_id, fe.analysis));
            setProgress(fe.progress);
            setDefectCounts({ ...fe.running_defect_counts });
            setHighSevCount(fe.high_severity_count);
            setSelectedFrame(fe.frame);

            // Auto-scroll filmstrip
            setTimeout(() => {
              filmstripRef.current?.scrollTo({
                left: filmstripRef.current.scrollWidth,
                behavior: "smooth",
              });
            }, 50);

            // Log defects
            if (fe.frame.defect_type !== "no_issue") {
              setLogs((prev) => [
                ...prev,
                `Frame ${fe.frame.frame_id}: ${fe.frame.defect_type} detected on ${fe.frame.asset_part} (severity: ${fe.frame.severity_score.toFixed(2)})`,
              ]);
            }
          } else if (currentEvent === "complete") {
            setCompleteSummary(data.summary);
            setLogs((prev) => [...prev, data.summary]);
          }
        }
      }
    }
    setRunning(false);
  };

  const sevColor = (s: number) =>
    s > 0.6 ? "#ef4444" : s > 0.3 ? "#eab308" : "#22c55e";

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>
        Live Inspection Viewer
      </h2>

      {/* Controls */}
      <div style={card}>
        <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Mission ID</label>
            <input
              value={missionId}
              onChange={(e) => setMissionId(e.target.value)}
              style={inputStyle}
              disabled={running}
            />
          </div>
          <button onClick={startLiveAnalysis} disabled={running} style={btnPrimary}>
            {running ? `Analyzing… ${progress.toFixed(0)}%` : "Start Live Analysis"}
          </button>
        </div>

        {/* Progress bar */}
        {running && (
          <div style={{ marginTop: 10, background: "#0B0F1A", borderRadius: 4, height: 6, overflow: "hidden" }}>
            <div
              style={{
                width: `${progress}%`,
                height: "100%",
                background: "linear-gradient(90deg, #06b6d4, #a78bfa)",
                transition: "width 0.3s",
                borderRadius: 4,
              }}
            />
          </div>
        )}
      </div>

      {/* KPI tiles */}
      {frames.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginTop: 12 }}>
          <KPI label="Frames" value={`${frames.length}`} color="#06b6d4" />
          <KPI
            label="Defects Found"
            value={`${Object.values(defectCounts).reduce((a, b) => a + b, 0)}`}
            color="#f97316"
          />
          <KPI label="High Severity" value={`${highSevCount}`} color="#ef4444" />
          <KPI
            label="Clean Frames"
            value={`${frames.filter((f) => f.defect_type === "no_issue").length}`}
            color="#22c55e"
          />
        </div>
      )}

      {/* Defect breakdown badges */}
      {Object.keys(defectCounts).length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
          {Object.entries(defectCounts).map(([type, count]) => (
            <DefectBadge key={type} type={type} count={count} />
          ))}
        </div>
      )}

      {/* Filmstrip + Detail */}
      {frames.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 12, marginTop: 12 }}>
          {/* Left: filmstrip grid */}
          <div style={card}>
            <h3 style={sectionTitle}>Frame Feed</h3>
            <div
              ref={filmstripRef}
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                gap: 6,
                marginTop: 8,
                maxHeight: 520,
                overflowY: "auto",
              }}
            >
              {frames.map((f) => (
                <div
                  key={f.frame_id}
                  onClick={() => setSelectedFrame(f)}
                  style={{
                    cursor: "pointer",
                    borderRadius: 6,
                    border: `2px solid ${
                      selectedFrame?.frame_id === f.frame_id
                        ? "#06b6d4"
                        : f.severity_score > 0.6
                        ? "#ef444466"
                        : f.severity_score > 0.3
                        ? "#eab30844"
                        : "#1E2D4F"
                    }`,
                    overflow: "hidden",
                    transition: "border-color 0.15s",
                  }}
                >
                  {f.image_path?.startsWith("/frames/") ? (
                    <img src={f.image_path} alt={f.frame_id} style={{ width: 140, height: 105, objectFit: "cover", display: "block", borderRadius: 4 }} />
                  ) : (
                    <UnderwaterFrame frame={f} size={140} showAnnotation={true} />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Right: selected frame detail */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {selectedFrame && (
              <>
                <div style={card}>
                  <h3 style={sectionTitle}>Frame Detail</h3>
                  <div style={{ marginTop: 8 }}>
                    {selectedFrame.image_path?.startsWith("/frames/") ? (
                      <img src={selectedFrame.image_path} alt={selectedFrame.frame_id}
                        style={{ width: "100%", maxWidth: 348, borderRadius: 6, display: "block" }} />
                    ) : (
                      <UnderwaterFrame frame={selectedFrame} size={348} showAnnotation={true} />
                    )}
                  </div>
                  <div style={{ marginTop: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 15, fontWeight: 700, color: "#e2e8f0" }}>
                        {selectedFrame.frame_id}
                      </span>
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: sevColor(selectedFrame.severity_score),
                          textTransform: "uppercase",
                        }}
                      >
                        {selectedFrame.defect_type.replace("_", " ")}
                      </span>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: 6,
                        marginTop: 8,
                      }}
                    >
                      <MiniStat label="Depth" value={`${selectedFrame.depth_m} m`} />
                      <MiniStat
                        label="Severity"
                        value={selectedFrame.severity_score.toFixed(3)}
                        color={sevColor(selectedFrame.severity_score)}
                      />
                      <MiniStat
                        label="Confidence"
                        value={`${(selectedFrame.model_output.confidence * 100).toFixed(0)}%`}
                      />
                      <MiniStat label="Visibility" value={`${selectedFrame.visual.visibility_m} m`} />
                      <MiniStat label="Part" value={selectedFrame.asset_part} />
                      <MiniStat
                        label="Pose"
                        value={`R${selectedFrame.camera_pose.roll} P${selectedFrame.camera_pose.pitch}`}
                      />
                    </div>
                  </div>
                </div>

                {/* Analysis text */}
                {analyses.has(selectedFrame.frame_id) && (
                  <div style={card}>
                    <h3 style={sectionTitle}>ML Analysis</h3>
                    <p
                      style={{
                        fontSize: 14,
                        color: "#94a3b8",
                        lineHeight: 1.6,
                        marginTop: 6,
                      }}
                    >
                      {analyses.get(selectedFrame.frame_id)}
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Analysis Log */}
      {logs.length > 0 && (
        <div style={{ ...card, marginTop: 12 }}>
          <h3 style={sectionTitle}>Analysis Log</h3>
          <div style={logBox}>
            {logs.map((l, i) => (
              <div key={i} style={{ color: "#94a3b8", fontSize: 13, lineHeight: 1.6 }}>
                <span style={{ color: l.includes("detected") ? "#ef4444" : "#06b6d4" }}>
                  &gt;
                </span>{" "}
                {l}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Complete summary */}
      {completeSummary && (
        <div
          style={{
            ...card,
            marginTop: 12,
            borderLeft: "3px solid #a78bfa",
          }}
        >
          <h3 style={sectionTitle}>Analysis Complete</h3>
          <p style={{ fontSize: 15, color: "#e2e8f0", marginTop: 6, lineHeight: 1.5 }}>
            {completeSummary}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────

function KPI({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div
      style={{
        background: "#141B2D",
        border: "1px solid #1E2D4F",
        borderRadius: 6,
        padding: "10px 12px",
        borderTop: `2px solid ${color}`,
      }}
    >
      <div style={{ fontSize: 12, color: "#64748b", fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  color = "#e2e8f0",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div style={{ background: "#0B0F1A", borderRadius: 4, padding: "4px 8px" }}>
      <div style={{ fontSize: 11, color: "#64748b" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color, marginTop: 1 }}>{value}</div>
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
const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "#64748b",
  marginBottom: 4,
};
const inputStyle: React.CSSProperties = {
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
  whiteSpace: "nowrap",
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
  maxHeight: 160,
  overflowY: "auto",
  border: "1px solid #1E2D4F",
};

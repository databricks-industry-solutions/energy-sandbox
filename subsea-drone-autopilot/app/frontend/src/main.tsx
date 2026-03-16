import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import FleetCommandPage from "./pages/FleetCommandPage";
import MissionPlannerPage from "./pages/MissionPlannerPage";
import InspectionReportPage from "./pages/InspectionReportPage";
import LiveInspectionPage from "./pages/LiveInspectionPage";
import DroneTwinPage from "./pages/DroneTwinPage";
import DataFlowPage from "./pages/DataFlowPage";
import KnowledgePage from "./pages/KnowledgePage";

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const loc = useLocation();
  const active = loc.pathname === to || (to !== "/" && loc.pathname.startsWith(to));
  return (
    <Link
      to={to}
      style={{
        color: active ? "#06b6d4" : "#cbd5e1",
        textDecoration: "none",
        fontSize: 15,
        fontWeight: 600,
        padding: "6px 14px",
        borderRadius: 5,
        background: active ? "#06b6d418" : "transparent",
        border: active ? "1px solid #06b6d433" : "1px solid transparent",
        transition: "all 0.15s",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </Link>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: "100vh", background: "#0B0F1A" }}>
        <nav
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "14px 28px",
            borderBottom: "1px solid #1E2D4F",
            background: "#0d1220",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 22, fontWeight: 700, color: "#06b6d4", marginRight: 16, whiteSpace: "nowrap" }}>
            <svg viewBox="0 0 32 24" width="32" height="24" style={{ flexShrink: 0 }}>
              {/* ROV icon */}
              <ellipse cx="16" cy="12" rx="13" ry="6" fill="none" stroke="#06b6d4" strokeWidth="1.5" />
              <ellipse cx="16" cy="11" rx="11" ry="4.5" fill="#06b6d420" />
              <circle cx="24" cy="12" r="3" fill="none" stroke="#3b82f6" strokeWidth="1" />
              <circle cx="24" cy="12" r="1.2" fill="#06b6d4" opacity="0.8" />
              <rect x="1" y="9" width="4" height="3" rx="1" fill="none" stroke="#f97316" strokeWidth="0.8" />
              <rect x="27" y="9" width="4" height="3" rx="1" fill="none" stroke="#f97316" strokeWidth="0.8" />
              <rect x="11" y="4" width="3" height="4" rx="1" fill="none" stroke="#a78bfa" strokeWidth="0.7" />
              <rect x="18" y="4" width="3" height="4" rx="1" fill="none" stroke="#a78bfa" strokeWidth="0.7" />
              <line x1="16" y1="3" x2="16" y2="0" stroke="#64748b" strokeWidth="1" strokeDasharray="1.5 1" />
            </svg>
            Subsea Autopilot
          </span>
          <NavLink to="/">Command</NavLink>
          <NavLink to="/fleet">Fleet Twin</NavLink>
          <NavLink to="/planner">Planner</NavLink>
          <NavLink to="/live">Live Viewer</NavLink>
          <NavLink to="/inspection">Report</NavLink>
          <NavLink to="/knowledge">Knowledge</NavLink>
          <NavLink to="/dataflow">Architecture</NavLink>
        </nav>

        <div style={{ padding: "20px 28px" }}>
          <Routes>
            <Route path="/" element={<FleetCommandPage />} />
            <Route path="/fleet" element={<DroneTwinPage />} />
            <Route path="/planner" element={<MissionPlannerPage />} />
            <Route path="/live" element={<LiveInspectionPage />} />
            <Route path="/live/:missionId" element={<LiveInspectionPage />} />
            <Route path="/inspection" element={<InspectionReportPage />} />
            <Route path="/inspection/:missionId" element={<InspectionReportPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/dataflow" element={<DataFlowPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

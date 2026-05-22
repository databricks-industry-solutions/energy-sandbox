import React, { useEffect, useRef, useState } from "react";

interface SpecialistInfo { id: string; name: string; feature: string; endpoint?: string; desc?: string }
interface SpecialistResult {
  id: string; name: string; feature: string; endpoint?: string;
  ms?: number; result?: string; query?: string; error?: string;
}
interface SupervisorInfo { name: string; model: string; specialists: SpecialistInfo[]; verdicts?: string[] }
interface Recommendation { rec_id: string; title?: string; priority?: string; affected_entities?: string }
interface Well { well_id: string; well_name?: string }

const PRESET_QUESTIONS = [
  "Approve this optimization recommendation?",
  "Defer until next maintenance window?",
  "Approve with modifications to reduce risk?",
];

type Status = "idle" | "running" | "done" | "error";

export default function SupervisorTab() {
  const [info, setInfo]         = useState<SupervisorInfo | null>(null);
  const [recs, setRecs]         = useState<Recommendation[]>([]);
  const [wells, setWells]       = useState<Well[]>([]);
  const [question, setQ]        = useState(PRESET_QUESTIONS[0]);
  const [recId, setRecId]       = useState<string>("");
  const [wellId, setWellId]     = useState<string>("");
  const [oilPrice, setOilPrice] = useState<number>(75);
  const [running, setRunning]   = useState(false);
  const [status, setStatus]     = useState<Record<string, Status>>({});
  const [results, setResults]   = useState<Record<string, SpecialistResult>>({});
  const [rec, setRec]           = useState<{ text: string; total_ms: number; verdict?: string } | null>(null);
  const [err, setErr]           = useState<string | null>(null);
  const abortRef                = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("/api/supervisor/info").then(r => r.json()).then(setInfo).catch(() => {});
    fetch("/api/production/recommendations")
      .then(r => r.ok ? r.json() : [])
      .then((data: any) => {
        const arr = Array.isArray(data) ? data : (data?.recommendations ?? []);
        if (arr.length) { setRecs(arr); setRecId(arr[0].rec_id || ""); }
      })
      .catch(() => {});
    fetch("/api/twin/state")
      .then(r => r.ok ? r.json() : null)
      .then((s: any) => {
        const ws = s?.wells || [];
        if (Array.isArray(ws) && ws.length) {
          setWells(ws.map((w: any) => ({ well_id: w.well_id || w.id, well_name: w.well_name || w.name })));
          if (ws[0]) setWellId(ws[0].well_id || ws[0].id || "");
        }
      })
      .catch(() => {});
  }, []);

  async function ask() {
    if (!question.trim() || running) return;
    setRunning(true); setRec(null); setErr(null); setResults({});
    const ac = new AbortController(); abortRef.current = ac;
    try {
      const resp = await fetch("/api/supervisor/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question, rec_id: recId || null, well_id: wellId || null, oil_price: oilPrice,
        }),
        signal: ac.signal,
      });
      if (!resp.body) throw new Error("no body");
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let nl: number;
        while ((nl = buf.indexOf("\n\n")) >= 0) {
          const chunk = buf.slice(0, nl); buf = buf.slice(nl + 2);
          let ev = "message", dataStr = "";
          for (const line of chunk.split("\n")) {
            if (line.startsWith("event:")) ev = line.slice(6).trim();
            else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
          }
          if (!dataStr) continue;
          let data: any;
          try { data = JSON.parse(dataStr); } catch { continue; }
          if (ev === "start") {
            const init: Record<string, Status> = {};
            for (const s of data.specialists || []) init[s.id] = "running";
            setStatus(init);
          } else if (ev === "specialist") {
            setResults(prev => ({ ...prev, [data.id]: data }));
            setStatus(prev => ({ ...prev, [data.id]: data.error ? "error" : "done" }));
          } else if (ev === "recommendation") {
            setRec({ text: data.text || "", total_ms: data.total_ms || 0, verdict: data.verdict });
          }
        }
      }
    } catch (e: any) {
      if (e.name !== "AbortError") setErr(String(e.message || e));
    } finally {
      setRunning(false); abortRef.current = null;
    }
  }

  function cancel() { abortRef.current?.abort(); setRunning(false); }

  const verdictColor = (v?: string) => {
    if (!v) return "#94a3b8";
    if (v === "APPROVE")           return "#22c55e";
    if (v === "APPROVE-WITH-MODS") return "#eab308";
    if (v === "DEFER")             return "#94a3b8";
    if (v === "REJECT")            return "#ef4444";
    return "#94a3b8";
  };

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto" }}>
      <div style={{
        background: "linear-gradient(135deg, #0a0e1a 0%, #150f2e 100%)",
        border: "1px solid #2d1b69", borderRadius: 14, padding: "18px 22px",
        marginBottom: 14, display: "flex", alignItems: "center", gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, minWidth: 48,
          background: "radial-gradient(circle at 30% 30%, #a78bfa, #7c3aed 70%)",
          border: "1.5px solid #a78bfa55", borderRadius: 24,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 24, boxShadow: "0 0 20px #7c3aed33",
        }}>🧠</div>
        <div style={{ flex: 1 }}>
          <div style={{ color: "#e2e8f0", fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em" }}>
            Recommendation Approval Supervisor
          </div>
          <div style={{ fontSize: 11, color: "#a78bfa", marginTop: 3, fontWeight: 500 }}>
            5 specialists in parallel — Foundation Model API · UC SQL × 3 · Vector Search
          </div>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {(info?.verdicts || ["APPROVE","MODS","DEFER","REJECT"]).map(v => (
            <span key={v} style={{
              border: "1px solid #334155", borderRadius: 10, padding: "3px 8px",
              fontSize: 10, color: "#94a3b8", fontWeight: 600,
            }}>{v}</span>
          ))}
        </div>
      </div>

      <div style={{
        background: "#0d1220", border: "1px solid #1E2D4F", borderRadius: 12,
        padding: 16, marginBottom: 14, display: "grid",
        gridTemplateColumns: "1fr 220px 180px 110px auto", gap: 10, alignItems: "end",
      }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 10, color: "#64748b" }}>Question</span>
          <input value={question} onChange={e => setQ(e.target.value)} style={inp} />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 10, color: "#64748b" }}>Recommendation</span>
          <select value={recId} onChange={e => setRecId(e.target.value)} style={inp}>
            <option value="">(none)</option>
            {recs.map(r => (
              <option key={r.rec_id} value={r.rec_id}>{r.rec_id} — {(r.title || "").slice(0, 30)}</option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 10, color: "#64748b" }}>Well</span>
          <select value={wellId} onChange={e => setWellId(e.target.value)} style={inp}>
            <option value="">(none)</option>
            {wells.map(w => (
              <option key={w.well_id} value={w.well_id}>{w.well_id}</option>
            ))}
          </select>
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 10, color: "#64748b" }}>Oil $/bbl</span>
          <input type="number" value={oilPrice} step={1} onChange={e => setOilPrice(+e.target.value)} style={inp} />
        </label>
        {running
          ? <button onClick={cancel} style={{ ...btn, background: "#ef4444", color: "#fff" }}>Cancel</button>
          : <button onClick={ask} disabled={!question.trim()} style={btn}>Run Supervisor</button>}
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
        {PRESET_QUESTIONS.map(q => (
          <button key={q} onClick={() => setQ(q)} style={chip}>{q}</button>
        ))}
      </div>

      {err && (
        <div style={{ padding: 10, background: "rgba(239,68,68,0.1)", border: "1px solid #ef4444",
                      borderRadius: 8, color: "#fca5a5", fontSize: 12, marginBottom: 14 }}>{err}</div>
      )}

      {rec && (
        <div style={{
          background: "#0d1220", border: "1px solid #1E2D4F", borderRadius: 12,
          padding: 16, marginBottom: 14, borderLeft: `4px solid ${verdictColor(rec.verdict)}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: verdictColor(rec.verdict), letterSpacing: "0.02em" }}>
              VERDICT — {rec.verdict || "REVIEW"}
            </div>
            <div style={{ fontSize: 10, color: "#64748b" }}>{rec.total_ms} ms total</div>
          </div>
          <div style={{ fontSize: 13, color: "#e2e8f0", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{rec.text}</div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12 }}>
        {(info?.specialists || []).map(s => {
          const r = results[s.id];
          const st = status[s.id] || "idle";
          const border = st === "done" ? "#22c55e" : st === "error" ? "#ef4444" : st === "running" ? "#eab308" : "#1E2D4F";
          return (
            <div key={s.id} style={{
              background: "#0d1220", border: "1px solid #1E2D4F", borderRadius: 10,
              padding: 12, borderLeft: `3px solid ${border}`,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#e2e8f0" }}>{s.name}</span>
                {r?.ms != null && <span style={{ fontSize: 10, color: "#64748b" }}>{r.ms} ms</span>}
              </div>
              <div style={{ fontSize: 10, color: "#64748b", marginBottom: 8 }}>
                {s.feature}{s.endpoint ? ` · ${s.endpoint}` : ""}
              </div>
              {st === "running" && <div style={{ fontSize: 11, color: "#eab308" }}>running…</div>}
              {st === "idle"    && <div style={{ fontSize: 11, color: "#475569" }}>{s.desc || "(waiting)"}</div>}
              {r?.error && <div style={{ fontSize: 11, color: "#fca5a5" }}>{r.error}</div>}
              {r?.result && (
                <pre style={{ fontSize: 11, color: "#cbd5e1", whiteSpace: "pre-wrap",
                              fontFamily: "inherit", margin: 0, lineHeight: 1.5 }}>{r.result}</pre>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const inp: React.CSSProperties = {
  padding: "8px 10px", background: "#0d1220", border: "1px solid #1E2D4F",
  borderRadius: 6, color: "#e2e8f0", fontSize: 12,
};
const btn: React.CSSProperties = {
  padding: "10px 18px", fontSize: 13, fontWeight: 600,
  background: "linear-gradient(135deg, #a78bfa, #7c3aed)",
  color: "#fff", border: "none", borderRadius: 8, cursor: "pointer",
};
const chip: React.CSSProperties = {
  fontSize: 11, padding: "5px 10px", border: "1px solid #1E2D4F",
  borderRadius: 14, background: "transparent", color: "#94a3b8", cursor: "pointer",
};

import React, { useEffect, useRef, useState } from "react";

interface Msg {
  role: "user" | "genie";
  text?: string;
  error?: string;
}

const SAMPLE_QUESTIONS = [
  "Top 5 recommendations by annual_revenue",
  "Which wells have the highest EUR?",
  "Show field netback and breakeven",
  "List high-priority recommendations with risk = low",
  "Decline curve fit quality (r_squared) per well",
  "Total daily revenue impact of all active recs",
];

export default function AskGeniePage() {
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [conv, setConv] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, loading]);

  async function ask(text: string) {
    if (!text.trim() || loading) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const resp = await fetch("/api/genie/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, conversation_id: conv }),
      });
      const data = await resp.json();
      if (data.error) {
        setMsgs((m) => [...m, { role: "genie", error: data.error }]);
      } else {
        setConv(data.conversation_id || conv);
        let answer = data.text || "(no response)";
        if (data.rows && data.rows.length > 0 && data.columns && data.columns.length > 0) {
          const cols = data.columns as string[];
          const rows = data.rows as any[][];
          const table = [
            "",
            "| " + cols.join(" | ") + " |",
            "|" + cols.map(() => "---").join("|") + "|",
            ...rows
              .slice(0, 15)
              .map((r) => "| " + r.map((v: any) => (v == null ? "" : String(v).slice(0, 60))).join(" | ") + " |"),
          ].join("\n");
          if (rows.length > 15) answer += `\n\n${table}\n\n_… ${rows.length - 15} more rows_`;
          else answer += `\n\n${table}`;
        }
        setMsgs((m) => [...m, { role: "genie", text: answer }]);
      }
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "genie", error: String(e.message || e) }]);
    } finally {
      setLoading(false);
    }
  }

  function clearChat() {
    setMsgs([]);
    setConv(null);
  }

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      {/* Hero */}
      <div style={{
        background: "linear-gradient(135deg, #0a0e1a 0%, #0d1729 100%)",
        border: "1px solid #1e293b", borderRadius: 14, padding: "18px 22px",
        marginBottom: 14, display: "flex", alignItems: "center", gap: 16,
      }}>
        <div style={{
          width: 48, height: 48, minWidth: 48,
          background: "radial-gradient(circle at 30% 30%, #67e8f9, #06b6d4 70%)",
          border: "1.5px solid #06b6d455", borderRadius: 24,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 24, boxShadow: "0 0 20px #06b6d433",
        }}>✨</div>
        <div style={{ flex: 1 }}>
          <div style={{ color: "#e2e8f0", fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em" }}>
            Ask Genie
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 3, fontWeight: 500 }}>
            Natural-language access to the production-optimizer data plane — wells, decline curves, recommendations, field economics.
          </div>
        </div>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          background: "#0c2333", border: "1px solid #06b6d444", borderRadius: 12,
          padding: "3px 9px", fontSize: 10, color: "#67e8f9", fontWeight: 600,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: 3, background: "#22c55e" }}></span>
          Genie · UC governed
        </span>
      </div>

      {msgs.length === 0 && (
        <div style={{
          background: "#0a0e1a", border: "1px dashed #1e293b", borderRadius: 12,
          padding: "28px 24px", textAlign: "center", margin: "10px 0 14px",
        }}>
          <div style={{ fontSize: 14, color: "#cbd5e1", fontWeight: 600, marginBottom: 6 }}>
            Ask anything about the field
          </div>
          <div style={{ fontSize: 11, color: "#64748b" }}>
            Genie translates your question to governed SQL against Unity Catalog tables:{" "}
            <code>bronze_wells</code>, <code>gold_decline_curves</code>,{" "}
            <code>gold_recommendations</code>, <code>gold_field_economics</code>,{" "}
            <code>silver_production_history</code>, <code>silver_economics</code>.
          </div>
        </div>
      )}

      <div ref={bodyRef} style={{
        background: "#0d1220", border: "1px solid #1E2D4F", borderRadius: 12,
        padding: 14, maxHeight: 540, overflowY: "auto", marginBottom: 12,
      }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ marginBottom: 12, display: "flex", gap: 10 }}>
            <div style={{
              width: 32, height: 32, minWidth: 32, borderRadius: 16,
              background: m.role === "user" ? "#1e293b" : "#0c2333",
              border: m.role === "user" ? "1px solid #334155" : "1px solid #06b6d455",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
            }}>{m.role === "user" ? "👤" : "✨"}</div>
            <div style={{ flex: 1, fontSize: 13, lineHeight: 1.6, color: "#e2e8f0" }}>
              {m.error ? (
                <div style={{ color: "#fca5a5" }}>⚠️ {m.error}</div>
              ) : (
                <div style={{ whiteSpace: "pre-wrap" }}><MarkdownLite text={m.text || ""} /></div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#67e8f9", fontSize: 12 }}>
            <span style={{
              width: 8, height: 8, borderRadius: 4, background: "#06b6d4",
              animation: "genie-pulse 1.1s infinite",
            }}></span>
            Genie is reasoning over the production data plane…
            <style>{`@keyframes genie-pulse { 0%,100% { opacity:.35 } 50% { opacity:1 } }`}</style>
          </div>
        )}
      </div>

      <div style={{
        fontSize: 10, color: "#64748b", fontWeight: 600,
        textTransform: "uppercase", margin: "8px 0 6px", letterSpacing: "0.03em",
      }}>Try one of these</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 12 }}>
        {SAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => ask(q)}
            disabled={loading}
            style={{
              fontSize: 11, padding: "8px 12px", borderRadius: 16,
              background: "#0f172a", border: "1px solid #1e293b",
              color: "#94a3b8", cursor: loading ? "not-allowed" : "pointer",
              textAlign: "left", transition: "all 0.15s",
            }}
          >{q}</button>
        ))}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ask(input); }} style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={loading ? "Genie is thinking…" : "Ask Genie about the field…"}
          disabled={loading}
          style={{
            flex: 1, background: "#0d1220", border: "1px solid #1E2D4F",
            borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#e2e8f0",
            opacity: loading ? 0.6 : 1,
          }}
        />
        <button type="submit" disabled={loading || !input.trim()} style={{
          padding: "10px 18px", fontSize: 13, fontWeight: 600,
          background: loading || !input.trim() ? "#0f172a" : "linear-gradient(135deg, #67e8f9, #06b6d4)",
          color: loading || !input.trim() ? "#475569" : "#0d1220",
          border: "none", borderRadius: 8,
          cursor: loading || !input.trim() ? "not-allowed" : "pointer",
        }}>Ask</button>
        {msgs.length > 0 && (
          <button type="button" onClick={clearChat} style={{
            padding: "10px 14px", fontSize: 12, background: "transparent",
            border: "1px solid #1E2D4F", borderRadius: 8, color: "#64748b", cursor: "pointer",
          }}>↺ Clear</button>
        )}
      </form>
    </div>
  );
}

function MarkdownLite({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  const lines = text.split("\n");
  let tableLines: string[] = [];

  const flushTable = () => {
    if (tableLines.length < 2) {
      tableLines.forEach((l) => parts.push(<div key={`p-${parts.length}`}>{renderInline(l)}</div>));
      tableLines = [];
      return;
    }
    const header = tableLines[0].split("|").map((c) => c.trim()).filter(Boolean);
    const rows = tableLines.slice(2).map((l) => l.split("|").map((c) => c.trim()).filter(Boolean));
    parts.push(
      <div key={`t-${parts.length}`} style={{ overflowX: "auto", margin: "8px 0" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 11, width: "100%" }}>
          <thead><tr>
            {header.map((h, i) => (
              <th key={i} style={{
                background: "#0f172a", color: "#94a3b8", padding: "6px 10px",
                border: "1px solid #1e293b", textAlign: "left", fontWeight: 600,
              }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j} style={{ padding: "5px 10px", border: "1px solid #1e293b", color: "#cbd5e1" }}>
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableLines = [];
  };

  for (const ln of lines) {
    if (ln.startsWith("|") && ln.endsWith("|")) tableLines.push(ln);
    else {
      if (tableLines.length) flushTable();
      parts.push(<div key={`l-${parts.length}`}>{renderInline(ln)}</div>);
    }
  }
  if (tableLines.length) flushTable();
  return <>{parts}</>;
}

function renderInline(s: string): React.ReactNode {
  const out: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m;
  let key = 0;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const tok = m[1];
    if (tok.startsWith("**")) out.push(<strong key={key++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) {
      out.push(
        <code key={key++} style={{
          background: "#0f172a", border: "1px solid #1e293b", borderRadius: 4,
          padding: "1px 6px", fontSize: 11, color: "#67e8f9",
        }}>{tok.slice(1, -1)}</code>
      );
    }
    last = m.index + tok.length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}

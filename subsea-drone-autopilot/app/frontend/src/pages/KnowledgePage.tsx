import React, { useState, useRef, useEffect } from "react";

interface Source {
  doc: string;
  section: string;
  relevance: string;
}

interface KnowledgeResponse {
  answer: string;
  sources: Source[];
  confidence: string;
  follow_up_suggestions: string[];
}

const QUICK_QUESTIONS = [
  "What are the criteria for recoating riser clamps?",
  "What is the thruster service interval for DRONE-01?",
  "Which drones are currently available for missions?",
  "What defects were found in the last inspection?",
  "What is the battery replacement procedure?",
  "What are the abort criteria for high-risk missions?",
];

export default function KnowledgePage() {
  const [question, setQuestion] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [result, setResult] = useState<KnowledgeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<{ q: string; a: KnowledgeResponse }[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  const askQuestion = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setLogs([]);
    setResult(null);
    setQuestion(q);

    const resp = await fetch("/api/knowledge/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
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
          try {
            const data = JSON.parse(line.slice(5).trim());
            if (currentEvent === "status") {
              setLogs((prev) => [...prev, data.message || "Processing..."]);
            } else if (currentEvent === "final") {
              // Extract answer from whatever format Claude returns
              let answer = "";
              if (typeof data === "string") {
                answer = data;
              } else if (data.answer) {
                answer = data.answer;
              } else if (data.summary) {
                answer = data.summary;
              } else if (data.content) {
                answer = data.content;
              } else if (data.status === "error") {
                answer = data.summary || "Agent encountered an error.";
              } else {
                // Last resort — format the JSON nicely
                answer = Object.entries(data)
                  .filter(([k]) => !["sources", "confidence", "follow_up_suggestions", "status"].includes(k))
                  .map(([k, v]) => `**${k}:** ${typeof v === "object" ? JSON.stringify(v) : v}`)
                  .join("\n\n");
                if (!answer) answer = JSON.stringify(data, null, 2);
              }

              const kr: KnowledgeResponse = {
                answer,
                sources: data.sources || [],
                confidence: data.confidence || "medium",
                follow_up_suggestions: data.follow_up_suggestions || [],
              };
              setResult(kr);
              setHistory((prev) => [...prev, { q, a: kr }]);
              setLoading(false);
            }
          } catch (parseErr) {
            setLogs((prev) => [...prev, line.slice(5).trim()]);
          }
        }
      }
    }
    setLoading(false);
  };

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [logs]);

  const confColor = (c: string) =>
    c === "high" ? "#22c55e" : c === "medium" ? "#eab308" : "#ef4444";

  return (
    <div>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 16 }}>
        Knowledge Assistant
      </h2>

      {/* Question input */}
      <div style={card}>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && askQuestion(question)}
            placeholder="Ask about procedures, fleet status, inspections, or standards…"
            style={{ ...inputStyle, flex: 1 }}
            disabled={loading}
          />
          <button onClick={() => askQuestion(question)} disabled={loading || !question.trim()} style={btnPrimary}>
            {loading ? "Searching…" : "Ask"}
          </button>
        </div>

        {/* Quick questions */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
          {QUICK_QUESTIONS.map((q, i) => (
            <button
              key={i}
              onClick={() => askQuestion(q)}
              disabled={loading}
              style={{
                padding: "4px 10px",
                borderRadius: 4,
                border: "1px solid #1E2D4F",
                background: "#0e1624",
                color: "#94a3b8",
                fontSize: 13,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Research log */}
      {logs.length > 0 && (
        <div style={{ ...card, marginTop: 12 }}>
          <h3 style={sectionTitle}>Research Log</h3>
          <div ref={logRef} style={logBox}>
            {logs.map((l, i) => (
              <div key={i} style={{ color: "#94a3b8", fontSize: 13, lineHeight: 1.6 }}>
                <span style={{ color: "#a78bfa" }}>&gt;</span> {l}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Answer */}
      {result && (
        <div style={{ ...card, marginTop: 12, borderLeft: "3px solid #06b6d4" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={sectionTitle}>Answer</h3>
            <span
              style={{
                fontSize: 12,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 4,
                background: confColor(result.confidence) + "22",
                color: confColor(result.confidence),
                border: `1px solid ${confColor(result.confidence)}55`,
              }}
            >
              {result.confidence.toUpperCase()} CONFIDENCE
            </span>
          </div>
          <div
            style={{
              fontSize: 15,
              color: "#e2e8f0",
              lineHeight: 1.7,
              marginTop: 10,
              whiteSpace: "pre-wrap",
            }}
          >
            {result.answer}
          </div>

          {/* Sources */}
          {result.sources.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                SOURCES
              </div>
              {result.sources.map((src, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    padding: "4px 8px",
                    background: "#0e1624",
                    borderRadius: 4,
                    marginBottom: 4,
                    fontSize: 13,
                  }}
                >
                  <span style={{ color: "#06b6d4", fontWeight: 700 }}>{src.doc}</span>
                  <span style={{ color: "#64748b" }}>{src.section}</span>
                  <span
                    style={{
                      marginLeft: "auto",
                      fontSize: 11,
                      color: src.relevance === "high" ? "#22c55e" : "#eab308",
                    }}
                  >
                    {src.relevance}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Follow-up suggestions */}
          {result.follow_up_suggestions.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>
                FOLLOW-UP QUESTIONS
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {result.follow_up_suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => askQuestion(s)}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 4,
                      border: "1px solid #6366f155",
                      background: "#6366f112",
                      color: "#a78bfa",
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Chat history */}
      {history.length > 1 && (
        <div style={{ ...card, marginTop: 12 }}>
          <h3 style={sectionTitle}>Previous Questions</h3>
          {history.slice(0, -1).reverse().map((h, i) => (
            <div
              key={i}
              style={{
                padding: "8px 10px",
                borderBottom: "1px solid #1E2D4F",
                cursor: "pointer",
              }}
              onClick={() => askQuestion(h.q)}
            >
              <div style={{ fontSize: 14, color: "#06b6d4", fontWeight: 600 }}>{h.q}</div>
              <div style={{ fontSize: 13, color: "#64748b", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {h.a.answer.slice(0, 120)}…
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const card: React.CSSProperties = {
  background: "#141B2D",
  border: "1px solid #1E2D4F",
  borderRadius: 8,
  padding: 20,
};
const inputStyle: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 6,
  border: "1px solid #1E2D4F",
  background: "#0B0F1A",
  color: "#e2e8f0",
  fontSize: 15,
};
const btnPrimary: React.CSSProperties = {
  padding: "10px 20px",
  borderRadius: 6,
  border: "none",
  background: "#a78bfa",
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
  maxHeight: 140,
  overflowY: "auto",
  border: "1px solid #1E2D4F",
};

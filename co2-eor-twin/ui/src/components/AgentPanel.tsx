import { useState, useEffect, useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  status: 'idle' | 'thinking' | 'busy' | 'error';
}

export interface Proposal {
  id: string;
  agentRole: string;
  description: string;
  impact?: string;
  risk?: 'low' | 'medium' | 'high';
  status: 'pending' | 'approved' | 'rejected';
}

interface AgentResponse {
  summary: string;
  contextCounts?: Record<string, number>;
  agentRole?: string;
}

interface FeatureProperties {
  [key: string]: unknown;
}

interface Props {
  selectedFeature: FeatureProperties | null;
  featureType?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const ROLE_CLASS: Record<string, string> = {
  reservoir: 'reservoir',
  production: 'production',
  environmental: 'environmental',
  commercial: 'commercial',
  safety: 'safety',
  logistics: 'logistics',
};

function roleClass(role: string): string {
  const lower = role.toLowerCase();
  for (const key of Object.keys(ROLE_CLASS)) {
    if (lower.includes(key)) return ROLE_CLASS[key];
  }
  return '';
}

/** Keys to hide from the properties panel. */
const HIDDEN_KEYS = new Set(['color', 'geometry', 'layerType', '_vectorTileFeature']);

function formatPropValue(val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'number') {
    return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  if (typeof val === 'boolean') return val ? 'Yes' : 'No';
  return String(val);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function AgentPanel({ selectedFeature, featureType }: Props) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [query, setQuery] = useState('');
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState<AgentResponse | null>(null);

  /* Fetch agents & proposals */
  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch('/api/twin/agents');
      if (!res.ok) return;
      const data = await res.json();
      setAgents(Array.isArray(data) ? data : data.agents ?? []);
    } catch {
      /* silent */
    }
  }, []);

  const fetchProposals = useCallback(async () => {
    try {
      const res = await fetch('/api/agent/proposals');
      if (!res.ok) return;
      const data = await res.json();
      const list: Proposal[] = Array.isArray(data) ? data : data.proposals ?? [];
      setProposals(list.filter((p) => p.status === 'pending'));
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    fetchAgents();
    fetchProposals();
    const iv = setInterval(() => {
      fetchAgents();
      fetchProposals();
    }, 10_000);
    return () => clearInterval(iv);
  }, [fetchAgents, fetchProposals]);

  /* Submit agent query */
  async function handleSend() {
    if (!query.trim() || sending) return;
    setSending(true);
    setResponse(null);
    try {
      const body: Record<string, unknown> = { prompt: query.trim() };
      if (selectedFeature) {
        body.selectedEntities = [selectedFeature];
      }
      const res = await fetch('/api/agent/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: AgentResponse = await res.json();
      setResponse(data);
    } catch (err) {
      setResponse({
        summary: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
      });
    } finally {
      setSending(false);
    }
  }

  /* Approve / Reject */
  async function handleProposalAction(id: string, action: 'approve' | 'reject') {
    try {
      await fetch(`/api/agent/proposal/${id}/${action}`, { method: 'POST' });
      setProposals((prev) => prev.filter((p) => p.id !== id));
    } catch {
      /* silent */
    }
  }

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */
  return (
    <>
      {/* --- Feature Properties --- */}
      <div className="panel-section">
        <div className="panel-section-header">
          <span>Selected Asset</span>
          {featureType && (
            <span className={`feature-type-badge ${featureType}`}>{featureType}</span>
          )}
        </div>
        <div className="panel-section-body">
          {selectedFeature ? (
            <div className="feature-props">
              {Object.entries(selectedFeature)
                .filter(([k]) => !HIDDEN_KEYS.has(k))
                .map(([key, val]) => (
                  <div className="feature-prop-row" key={key}>
                    <span className="feature-prop-key">{key}</span>
                    <span className="feature-prop-value">{formatPropValue(val)}</span>
                  </div>
                ))}
            </div>
          ) : (
            <div className="no-selection">Click a map feature to inspect</div>
          )}
        </div>
      </div>

      {/* --- Agent Status --- */}
      <div className="panel-section">
        <div className="panel-section-header">Agents</div>
        <div className="panel-section-body">
          <div className="agent-chips">
            {agents.length === 0 && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                No agents connected
              </span>
            )}
            {agents.map((agent) => (
              <div
                key={agent.id}
                className={`agent-chip ${roleClass(agent.role)}`}
                title={`${agent.name} — ${agent.status}`}
              >
                <span className={`status-dot ${agent.status}`} />
                <span>{agent.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* --- Agent Query --- */}
      <div className="panel-section" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="panel-section-header">Query Agent</div>
        <div className="panel-section-body" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="agent-query-area" style={{ flex: 1 }}>
            <textarea
              className="agent-textarea"
              placeholder="Ask about well performance, injection strategy, CO&#x2082; balance..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSend();
              }}
            />
            <button
              className="agent-send-btn"
              disabled={!query.trim() || sending}
              onClick={handleSend}
            >
              {sending ? 'Thinking...' : 'Ask Agent'}
            </button>

            {response && (
              <div className="agent-response">
                {response.agentRole && (
                  <div className="agent-response-role">{response.agentRole}</div>
                )}
                <div className="agent-response-text">{response.summary}</div>
                {response.contextCounts && Object.keys(response.contextCounts).length > 0 && (
                  <div className="agent-context-counts">
                    {Object.entries(response.contextCounts).map(([key, count]) => (
                      <span key={key} className="context-count-badge">
                        {key}: {count}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* --- Proposals --- */}
      {proposals.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-header">
            <span>Pending Proposals</span>
            <span className="context-count-badge">{proposals.length}</span>
          </div>
          <div className="panel-section-body">
            <div className="proposals-list">
              {proposals.map((p) => (
                <div key={p.id} className="proposal-card">
                  <div className="proposal-header">
                    <span className="proposal-agent">{p.agentRole}</span>
                    {p.risk && (
                      <span className={`proposal-risk ${p.risk}`}>{p.risk}</span>
                    )}
                  </div>
                  <div className="proposal-text">{p.description}</div>
                  {p.impact && <div className="proposal-impact">{p.impact}</div>}
                  <div className="proposal-actions">
                    <button
                      className="proposal-btn approve"
                      onClick={() => handleProposalAction(p.id, 'approve')}
                    >
                      Approve
                    </button>
                    <button
                      className="proposal-btn reject"
                      onClick={() => handleProposalAction(p.id, 'reject')}
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

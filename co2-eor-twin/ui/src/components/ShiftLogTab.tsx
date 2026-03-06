import { useState, useEffect, useCallback, CSSProperties, FormEvent } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ShiftEntry {
  timestamp: string;
  category: string;
  message: string;
  entityId?: string;
  agentId?: string;
}

interface ShiftData {
  id: string;
  shift: string;
  date: string;
  operator: string;
  entries: ShiftEntry[];
}

interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical' | 'emergency';
  message: string;
  timestamp: string;
  source?: string;
  acknowledged?: boolean;
}

/* ------------------------------------------------------------------ */
/*  Styles                                                             */
/* ------------------------------------------------------------------ */

const S: Record<string, CSSProperties> = {
  layout: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    padding: 16,
    gap: 16,
    overflowY: 'auto',
    background: 'var(--bg-root)',
  },
  shiftCard: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    padding: '14px 18px',
    background: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
  },
  shiftBadge: {
    fontFamily: 'var(--font-mono)',
    fontSize: 18,
    fontWeight: 700,
    color: 'var(--accent)',
  },
  shiftMeta: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  shiftMetaLabel: {
    fontSize: 11,
    color: 'var(--text-muted)',
  },
  shiftMetaValue: {
    fontSize: 13,
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-primary)',
  },
  divider: {
    width: 1,
    height: 32,
    background: 'var(--border)',
    flexShrink: 0,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    color: 'var(--text-muted)',
    marginBottom: 2,
  },
  mainArea: {
    display: 'grid',
    gridTemplateColumns: '1fr 320px',
    gap: 16,
    flex: 1,
    minHeight: 0,
  },
  timelineCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    overflowY: 'auto',
  },
  entryCard: {
    display: 'flex',
    gap: 12,
    padding: '10px 14px',
    background: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    alignItems: 'flex-start',
  },
  entryTime: {
    fontFamily: 'var(--font-mono)',
    fontSize: 11,
    color: 'var(--text-muted)',
    flexShrink: 0,
    minWidth: 50,
    paddingTop: 1,
  },
  entryBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    flex: 1,
  },
  entryMessage: {
    fontSize: 12,
    color: 'var(--text-secondary)',
    lineHeight: 1.4,
  },
  entryMeta: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
  },
  entryMetaTag: {
    fontFamily: 'var(--font-mono)',
    fontSize: 10,
    color: 'var(--text-muted)',
    padding: '1px 6px',
    background: 'var(--bg-card)',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
  },
  categoryBadge: {
    fontSize: 10,
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: 'var(--radius-sm)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
    flexShrink: 0,
  },
  sidebar: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    overflowY: 'auto',
  },
  formPanel: {
    background: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '14px 18px',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  textarea: {
    width: '100%',
    minHeight: 70,
    maxHeight: 140,
    resize: 'vertical' as const,
    padding: '8px 10px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border)',
    background: 'var(--bg-input)',
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-sans)',
    fontSize: 12,
    lineHeight: 1.4,
    outline: 'none',
  },
  select: {
    width: '100%',
    padding: '6px 10px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border)',
    background: 'var(--bg-input)',
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-sans)',
    fontSize: 12,
    outline: 'none',
  },
  submitBtn: {
    alignSelf: 'flex-end',
    padding: '6px 16px',
    borderRadius: 'var(--radius-md)',
    border: 'none',
    background: 'var(--accent)',
    color: '#0f1117',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'var(--font-sans)',
  },
  alertsPanel: {
    background: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '14px 18px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    flex: 1,
    overflowY: 'auto',
  },
  alertItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
    padding: '6px 8px',
    borderRadius: 'var(--radius-sm)',
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
  },
  alertDot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    flexShrink: 0,
    marginTop: 4,
  },
  alertText: {
    fontSize: 11,
    color: 'var(--text-secondary)',
    lineHeight: 1.3,
    flex: 1,
  },
  alertTime: {
    fontFamily: 'var(--font-mono)',
    fontSize: 10,
    color: 'var(--text-muted)',
    flexShrink: 0,
  },
  loadingWrap: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: 10,
    color: 'var(--text-muted)',
    fontSize: 13,
  },
  errorWrap: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: 'var(--danger)',
    fontSize: 13,
  },
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const CATEGORY_STYLES: Record<string, CSSProperties> = {
  operations: { background: 'var(--blue-dim)', color: 'var(--blue)' },
  safety: { background: 'var(--danger-dim)', color: 'var(--danger)' },
  maintenance: { background: 'var(--warning-dim)', color: 'var(--warning)' },
  agent_action: { background: 'var(--co2-dim)', color: 'var(--co2)' },
  handoff: { background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' },
};

function getCategoryStyle(cat: string): CSSProperties {
  return CATEGORY_STYLES[cat?.toLowerCase()] ?? {
    background: 'var(--bg-card)',
    color: 'var(--text-secondary)',
  };
}

const SEVERITY_COLORS: Record<string, string> = {
  info: 'var(--blue)',
  warning: 'var(--warning)',
  critical: 'var(--orange)',
  emergency: 'var(--danger)',
};

function formatTime(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return ts;
  }
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return ts;
  }
}

const CATEGORIES = [
  'operations',
  'safety',
  'maintenance',
  'agent_action',
  'handoff',
] as const;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function ShiftLogTab() {
  const [shift, setShift] = useState<ShiftData | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* New entry form state */
  const [newMessage, setNewMessage] = useState('');
  const [newCategory, setNewCategory] = useState<string>('operations');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [shiftRes, alertRes] = await Promise.all([
        fetch('/api/shift/current'),
        fetch('/api/twin/alerts'),
      ]);
      if (!shiftRes.ok) throw new Error(`Shift data: HTTP ${shiftRes.status}`);
      const shiftData = await shiftRes.json();
      setShift(shiftData);

      if (alertRes.ok) {
        const alertData = await alertRes.json();
        setAlerts(Array.isArray(alertData) ? alertData : alertData.alerts ?? []);
      }
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load data';
      setError(msg);
      console.warn('ShiftLogTab fetch error:', msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 15_000);
    return () => clearInterval(iv);
  }, [fetchData]);

  /* Submit new log entry */
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim() || submitting) return;

    setSubmitting(true);
    try {
      const res = await fetch('/api/shift/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: newCategory,
          message: newMessage.trim(),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setNewMessage('');
      /* Refresh shift data to show new entry */
      fetchData();
    } catch (err) {
      console.warn('Failed to submit log entry:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={S.loadingWrap}>
        <div className="loading-spinner" />
        <span>Loading shift log...</span>
      </div>
    );
  }

  if (error || !shift) {
    return (
      <div style={S.errorWrap}>
        <span>&#9888; {error || 'No shift data available'}</span>
      </div>
    );
  }

  const entries = shift.entries ?? [];
  const recentAlerts = alerts
    .filter((a) => !a.acknowledged)
    .slice(0, 15);

  return (
    <div style={S.layout}>
      {/* ---- Shift info card ---- */}
      <div style={S.shiftCard}>
        <span style={S.shiftBadge}>{shift.shift}</span>
        <div style={S.divider} />
        <div style={S.shiftMeta}>
          <span style={S.shiftMetaLabel}>Date</span>
          <span style={S.shiftMetaValue}>{shift.date}</span>
        </div>
        <div style={S.divider} />
        <div style={S.shiftMeta}>
          <span style={S.shiftMetaLabel}>Operator</span>
          <span style={S.shiftMetaValue}>{shift.operator}</span>
        </div>
        <div style={S.divider} />
        <div style={S.shiftMeta}>
          <span style={S.shiftMetaLabel}>Log Entries</span>
          <span style={S.shiftMetaValue}>{entries.length}</span>
        </div>
      </div>

      {/* ---- Main area: Timeline + Sidebar ---- */}
      <div style={S.mainArea}>
        {/* Timeline column */}
        <div style={S.timelineCol}>
          <span style={S.sectionTitle}>Shift Timeline</span>
          {entries.map((entry, i) => (
            <div key={i} style={S.entryCard}>
              <span style={S.entryTime}>{formatTime(entry.timestamp)}</span>
              <span
                style={{ ...S.categoryBadge, ...getCategoryStyle(entry.category) }}
              >
                {entry.category}
              </span>
              <div style={S.entryBody}>
                <span style={S.entryMessage}>{entry.message}</span>
                {(entry.entityId || entry.agentId) && (
                  <div style={S.entryMeta}>
                    {entry.entityId && (
                      <span style={S.entryMetaTag}>Entity: {entry.entityId}</span>
                    )}
                    {entry.agentId && (
                      <span style={S.entryMetaTag}>Agent: {entry.agentId}</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {entries.length === 0 && (
            <div
              style={{
                textAlign: 'center',
                padding: 40,
                color: 'var(--text-muted)',
                fontSize: 13,
              }}
            >
              No entries for this shift yet
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div style={S.sidebar}>
          {/* Add entry form */}
          <div style={S.formPanel}>
            <span style={S.sectionTitle}>Add Log Entry</span>
            <form
              onSubmit={handleSubmit}
              style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              <textarea
                style={S.textarea}
                placeholder="Enter shift log message..."
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
              />
              <select
                style={S.select}
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.replace('_', ' ')}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                style={{
                  ...S.submitBtn,
                  opacity: submitting || !newMessage.trim() ? 0.4 : 1,
                  cursor:
                    submitting || !newMessage.trim() ? 'not-allowed' : 'pointer',
                }}
                disabled={submitting || !newMessage.trim()}
              >
                {submitting ? 'Submitting...' : 'Add Entry'}
              </button>
            </form>
          </div>

          {/* Recent alerts */}
          <div style={S.alertsPanel}>
            <span style={S.sectionTitle}>
              Recent Alerts ({recentAlerts.length})
            </span>
            {recentAlerts.map((alert) => (
              <div key={alert.id} style={S.alertItem}>
                <div
                  style={{
                    ...S.alertDot,
                    background: SEVERITY_COLORS[alert.severity] ?? 'var(--blue)',
                  }}
                />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span
                    style={{
                      ...S.alertText,
                      color: SEVERITY_COLORS[alert.severity] ?? 'var(--text-secondary)',
                    }}
                  >
                    {alert.message}
                  </span>
                  {alert.source && (
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      {alert.source}
                    </span>
                  )}
                </div>
                <span style={S.alertTime}>{formatTimestamp(alert.timestamp)}</span>
              </div>
            ))}
            {recentAlerts.length === 0 && (
              <div
                style={{
                  textAlign: 'center',
                  padding: 20,
                  color: 'var(--text-muted)',
                  fontSize: 12,
                }}
              >
                No active alerts
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

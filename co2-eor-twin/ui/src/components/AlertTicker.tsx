import type { Alert } from '../App';

interface Props {
  alerts: Alert[];
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function AlertTicker({ alerts }: Props) {
  /* Show the latest alerts, most recent first */
  const visible = alerts
    .filter((a) => !a.acknowledged)
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 8);

  return (
    <div className="alert-ticker">
      <span className="alert-ticker-label">Alerts</span>
      <div className="alert-ticker-items">
        {visible.length === 0 && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            No active alerts
          </span>
        )}
        {visible.map((alert) => (
          <div key={alert.id} className="alert-ticker-item" title={alert.message}>
            <span className={`alert-severity-dot ${alert.severity}`} />
            <span className="alert-time">{formatTime(alert.timestamp)}</span>
            <span className={`alert-msg ${alert.severity}`}>{alert.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

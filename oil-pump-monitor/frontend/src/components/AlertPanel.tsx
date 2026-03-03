import React from 'react';
import { AlertTriangle, XCircle, Bell } from 'lucide-react';
import type { VibrationReading } from '../types';

interface Alert extends VibrationReading {
  pump_name?: string;
}

interface Props {
  alerts: Alert[];
}

export function AlertPanel({ alerts }: Props) {
  return (
    <div style={{ background: '#0f172a', borderRadius: 12, border: '1px solid #1e293b', padding: 16, height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Bell size={14} color='#f97316' />
        <span style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Recent Alerts
        </span>
        {alerts.length > 0 && (
          <span style={{
            background: '#ef444422', border: '1px solid #ef4444',
            borderRadius: 10, padding: '1px 7px', fontSize: 10, color: '#f87171', marginLeft: 'auto'
          }}>
            {alerts.length}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div style={{ color: '#475569', fontSize: 13, textAlign: 'center', padding: '30px 0' }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>✓</div>
          All pumps nominal
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 280, overflowY: 'auto' }}>
          {alerts.map((alert, i) => (
            <div key={i} style={{
              background: alert.alert_level === 'critical' ? '#1a000022' : '#1a140022',
              border: `1px solid ${alert.alert_level === 'critical' ? '#7f1d1d' : '#78350f'}`,
              borderRadius: 8, padding: '8px 12px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  {alert.alert_level === 'critical'
                    ? <XCircle size={11} color='#ef4444' />
                    : <AlertTriangle size={11} color='#eab308' />}
                  <span style={{ fontSize: 12, fontWeight: 600, color: alert.alert_level === 'critical' ? '#f87171' : '#facc15' }}>
                    {alert.pump_name ?? alert.pump_id}
                  </span>
                </div>
                <span style={{ fontSize: 10, color: '#475569' }}>
                  {new Date(alert.timestamp).toLocaleTimeString('en-US', { hour12: false })}
                </span>
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', display: 'flex', gap: 12 }}>
                <span>Amp: <b style={{ color: '#e2e8f0' }}>{alert.amplitude_mm_s?.toFixed(2)} mm/s</b></span>
                <span>RPM: <b style={{ color: '#e2e8f0' }}>{alert.rpm}</b></span>
                <span>Temp: <b style={{ color: '#e2e8f0' }}>{alert.temperature_f?.toFixed(0)}°F</b></span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

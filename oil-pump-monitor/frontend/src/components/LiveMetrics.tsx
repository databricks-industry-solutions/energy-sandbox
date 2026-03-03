import React from 'react';
import { Activity, Thermometer, Gauge, Zap, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import type { VibrationReading } from '../types';

interface Props {
  reading: VibrationReading | null;
  pumpName: string;
}

const alertColors = {
  normal: { bg: '#0d2137', border: '#1a4a6e', badge: '#22c55e', text: '#4ade80' },
  warning: { bg: '#1a1400', border: '#78350f', badge: '#eab308', text: '#facc15' },
  critical: { bg: '#1a0000', border: '#7f1d1d', badge: '#ef4444', text: '#f87171' },
};

function Metric({ label, value, unit, icon: Icon, color = '#38bdf8' }: {
  label: string; value: string | number; unit: string; icon: React.ElementType; color?: string;
}) {
  return (
    <div style={{
      background: '#0f172a', borderRadius: 8, padding: '12px 16px',
      border: '1px solid #1e293b', flex: 1, minWidth: 110
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <Icon size={14} color={color} />
        <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1 }}>
        {typeof value === 'number' ? value.toFixed(1) : value}
        <span style={{ fontSize: 12, color: '#64748b', fontWeight: 400, marginLeft: 3 }}>{unit}</span>
      </div>
    </div>
  );
}

export function LiveMetrics({ reading, pumpName }: Props) {
  const level = reading?.alert_level ?? 'normal';
  const colors = alertColors[level];

  return (
    <div style={{
      background: colors.bg, border: `1px solid ${colors.border}`,
      borderRadius: 12, padding: 16, marginBottom: 16
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={16} color='#38bdf8' />
          <span style={{ fontWeight: 600, fontSize: 14 }}>{pumpName}</span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5,
          background: colors.badge + '22', border: `1px solid ${colors.badge}`,
          borderRadius: 20, padding: '2px 10px', fontSize: 11, color: colors.text
        }}>
          {level === 'normal' ? <CheckCircle size={11} /> :
           level === 'warning' ? <AlertTriangle size={11} /> :
           <XCircle size={11} />}
          {level.toUpperCase()}
        </div>
      </div>

      {reading ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Metric label="Frequency" value={reading.frequency_hz} unit="Hz" icon={Activity} color='#38bdf8' />
          <Metric label="Amplitude" value={reading.amplitude_mm_s} unit="mm/s" icon={Zap}
            color={reading.amplitude_mm_s > 4 ? '#ef4444' : reading.amplitude_mm_s > 3 ? '#eab308' : '#a78bfa'} />
          <Metric label="RPM" value={reading.rpm} unit="rpm" icon={Gauge} color='#34d399' />
          <Metric label="Temp" value={reading.temperature_f} unit="°F" icon={Thermometer}
            color={reading.temperature_f > 170 ? '#ef4444' : reading.temperature_f > 160 ? '#eab308' : '#f97316'} />
          <Metric label="Pressure" value={reading.pressure_psi} unit="PSI" icon={Gauge} color='#f472b6' />
        </div>
      ) : (
        <div style={{ color: '#475569', fontSize: 13, textAlign: 'center', padding: 20 }}>
          Waiting for sensor data...
        </div>
      )}
    </div>
  );
}

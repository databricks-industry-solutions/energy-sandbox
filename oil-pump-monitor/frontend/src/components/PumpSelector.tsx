import React from 'react';
import type { FieldSummaryItem } from '../types';

interface Props {
  pumps: FieldSummaryItem[];
  selectedPump: string | null;
  onSelect: (id: string) => void;
}

const levelColor = {
  normal: '#22c55e',
  warning: '#eab308',
  critical: '#ef4444',
};

export function PumpSelector({ pumps, selectedPump, onSelect }: Props) {
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
      {pumps.map(pump => {
        const color = levelColor[pump.alert_level as keyof typeof levelColor] ?? '#22c55e';
        const isSelected = pump.pump_id === selectedPump;
        return (
          <button
            key={pump.pump_id}
            onClick={() => onSelect(pump.pump_id)}
            style={{
              background: isSelected ? '#1e3a5f' : '#0f172a',
              border: `1px solid ${isSelected ? '#38bdf8' : '#1e293b'}`,
              borderRadius: 8, padding: '8px 14px', cursor: 'pointer',
              color: isSelected ? '#e2e8f0' : '#94a3b8',
              fontSize: 12, fontWeight: isSelected ? 600 : 400,
              display: 'flex', alignItems: 'center', gap: 6,
              transition: 'all 0.15s',
            }}
          >
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: color,
              boxShadow: pump.alert_level !== 'normal' ? `0 0 6px ${color}` : 'none' }} />
            {pump.pump_id.replace('PUMP-ND-', 'P')}
            {pump.amplitude_mm_s != null && (
              <span style={{ fontSize: 10, color: '#475569' }}>
                {(pump.amplitude_mm_s as number).toFixed(1)}mm/s
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

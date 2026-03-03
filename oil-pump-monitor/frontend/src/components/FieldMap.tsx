import React from 'react';
import { MapPin, AlertTriangle } from 'lucide-react';
import type { FieldSummaryItem } from '../types';

interface Props {
  pumps: FieldSummaryItem[];
  selectedPump: string | null;
  onSelect: (id: string) => void;
}

// North Dakota Bakken region: lat 47.5-48.7, lon -104.5 to -101.5
const MAP_LAT_MIN = 47.4, MAP_LAT_MAX = 48.8;
const MAP_LON_MIN = -104.6, MAP_LON_MAX = -101.0;

function toPercent(val: number, min: number, max: number) {
  return ((val - min) / (max - min)) * 100;
}

const alertStyle: Record<string, { color: string; glow: string }> = {
  normal: { color: '#22c55e', glow: '#22c55e44' },
  warning: { color: '#eab308', glow: '#eab30844' },
  critical: { color: '#ef4444', glow: '#ef444444' },
};

export function FieldMap({ pumps, selectedPump, onSelect }: Props) {
  return (
    <div style={{
      background: '#0a0e1a', borderRadius: 12, border: '1px solid #1e293b',
      padding: 16, height: '100%', minHeight: 340
    }}>
      <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>North Dakota Bakken Field Map</span>
        <span style={{ color: '#475569', fontSize: 10 }}>Williston Basin</span>
      </div>

      {/* Map container */}
      <div style={{ position: 'relative', width: '100%', paddingBottom: '55%' }}>
        {/* Background grid lines (simulating map) */}
        <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
          viewBox="0 0 100 55" preserveAspectRatio="none">
          {/* Background */}
          <rect width="100" height="55" fill="#0d1829" rx="0" />
          {/* Grid */}
          {[0.2, 0.4, 0.6, 0.8].map(x => (
            <line key={x} x1={x * 100} y1="0" x2={x * 100} y2="55"
              stroke="#1e293b" strokeWidth="0.3" />
          ))}
          {[0.25, 0.5, 0.75].map(y => (
            <line key={y} x1="0" y1={y * 55} x2="100" y2={y * 55}
              stroke="#1e293b" strokeWidth="0.3" />
          ))}
          {/* ND state border (simplified) */}
          <rect x="1" y="1" width="98" height="53" fill="none" stroke="#334155" strokeWidth="0.6" rx="1" />
          {/* Williston label */}
          <text x="28" y="20" fill="#1e3a5f" fontSize="3.5" fontFamily="system-ui">WILLISTON</text>
          <text x="28" y="24" fill="#1e3a5f" fontSize="3.5" fontFamily="system-ui">BASIN</text>
          {/* Missouri River (simplified) */}
          <path d="M10,40 Q30,35 50,42 Q70,49 90,45" fill="none" stroke="#1e3a5f" strokeWidth="0.8" />
          <text x="60" y="50" fill="#1e3a5f" fontSize="2.5" fontFamily="system-ui">Missouri R.</text>
          {/* Legend */}
          <text x="2" y="54" fill="#334155" fontSize="2" fontFamily="system-ui">47.5°N</text>
          <text x="2" y="3" fill="#334155" fontSize="2" fontFamily="system-ui">48.7°N</text>
          <text x="75" y="54" fill="#334155" fontSize="2" fontFamily="system-ui">101.5°W</text>
          <text x="2" y="54" fill="#334155" fontSize="2" fontFamily="system-ui"></text>
        </svg>

        {/* Pump markers */}
        {pumps.map(pump => {
          if (!pump.latitude || !pump.longitude) return null;
          const x = toPercent(pump.longitude, MAP_LON_MIN, MAP_LON_MAX);
          const y = 100 - toPercent(pump.latitude, MAP_LAT_MIN, MAP_LAT_MAX);
          const style = alertStyle[pump.alert_level ?? 'normal'];
          const isSelected = pump.pump_id === selectedPump;

          return (
            <div
              key={pump.pump_id}
              onClick={() => onSelect(pump.pump_id)}
              title={`${pump.name}\n${pump.alert_level?.toUpperCase()}`}
              style={{
                position: 'absolute',
                left: `${x}%`, top: `${y}%`,
                transform: 'translate(-50%, -50%)',
                cursor: 'pointer',
                zIndex: isSelected ? 10 : 5,
              }}
            >
              {/* Pulse ring */}
              {pump.alert_level !== 'normal' && (
                <div style={{
                  position: 'absolute', top: '50%', left: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: isSelected ? 28 : 22, height: isSelected ? 28 : 22,
                  borderRadius: '50%', background: style.glow,
                  animation: 'pulse 1.5s infinite',
                }} />
              )}
              <div style={{
                width: isSelected ? 16 : 12, height: isSelected ? 16 : 12,
                borderRadius: '50%',
                background: style.color,
                border: `2px solid ${isSelected ? '#fff' : style.color}`,
                boxShadow: `0 0 ${isSelected ? 10 : 6}px ${style.glow}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                position: 'relative',
              }}>
                {pump.alert_level === 'critical' && (
                  <div style={{ width: 4, height: 4, background: '#fff', borderRadius: '50%' }} />
                )}
              </div>
              {/* Label */}
              <div style={{
                position: 'absolute', top: '100%', left: '50%',
                transform: 'translateX(-50%)', marginTop: 2,
                fontSize: 8, color: isSelected ? '#e2e8f0' : '#64748b',
                whiteSpace: 'nowrap', fontWeight: isSelected ? 600 : 400,
                background: '#0a0e1a88', padding: '1px 3px', borderRadius: 3,
              }}>
                {pump.pump_id.replace('PUMP-ND-', 'P')}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginTop: 12, justifyContent: 'center' }}>
        {Object.entries(alertStyle).map(([level, s]) => (
          <div key={level} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#64748b' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.color }} />
            {level.charAt(0).toUpperCase() + level.slice(1)}
          </div>
        ))}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.8; transform: translate(-50%, -50%) scale(1); }
          50% { opacity: 0.2; transform: translate(-50%, -50%) scale(1.5); }
        }
      `}</style>
    </div>
  );
}

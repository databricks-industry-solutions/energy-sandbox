import React, { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import type { VibrationReading } from '../types';

interface Props {
  history: VibrationReading[];
  metric: 'amplitude_mm_s' | 'frequency_hz' | 'rpm' | 'temperature_f' | 'pressure_psi';
  label: string;
  unit: string;
  color?: string;
  warningThreshold?: number;
  criticalThreshold?: number;
}

export function WaveformChart({ history, metric, label, unit, color = '#38bdf8', warningThreshold, criticalThreshold }: Props) {
  const data = useMemo(() =>
    history.slice(-120).map((r, i) => ({
      t: i,
      value: r[metric] as number,
      ts: new Date(r.timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      anomaly: r.is_anomaly,
    })),
    [history, metric]
  );

  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    if (!payload.anomaly) return null;
    return <circle cx={cx} cy={cy} r={4} fill='#ef4444' stroke='#fca5a5' strokeWidth={1.5} />;
  };

  return (
    <div style={{ background: '#0f172a', borderRadius: 10, padding: '16px', border: '1px solid #1e293b' }}>
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 4" stroke='#1e293b' />
          <XAxis dataKey="ts" tick={{ fontSize: 9, fill: '#475569' }} interval={29} />
          <YAxis tick={{ fontSize: 9, fill: '#475569' }} />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6, fontSize: 11 }}
            formatter={(v: number) => [`${v.toFixed(3)} ${unit}`, label]}
            labelFormatter={(l) => `Time: ${l}`}
          />
          {warningThreshold && (
            <ReferenceLine y={warningThreshold} stroke='#eab308' strokeDasharray="3 3" strokeWidth={1} />
          )}
          {criticalThreshold && (
            <ReferenceLine y={criticalThreshold} stroke='#ef4444' strokeDasharray="3 3" strokeWidth={1} />
          )}
          <Line
            type="monotone" dataKey="value"
            stroke={color} strokeWidth={1.5} dot={<CustomDot />}
            activeDot={{ r: 4, fill: color }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import type { SpectrumReading } from '../types';

interface Props {
  spectrum: SpectrumReading | null;
  baseFreq?: number;
}

export function SpectrumChart({ spectrum, baseFreq }: Props) {
  if (!spectrum) {
    return (
      <div style={{ background: '#0f172a', borderRadius: 10, padding: 16, border: '1px solid #1e293b', height: 180 }}>
        <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Frequency Spectrum (FFT)
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 140, color: '#475569', fontSize: 13 }}>
          Loading spectrum...
        </div>
      </div>
    );
  }

  const data = spectrum.frequencies.map((f, i) => ({
    freq: f.toFixed(1),
    amp: spectrum.amplitudes[i],
  }));

  const harmonics = baseFreq ? [baseFreq, baseFreq * 2, baseFreq * 3, baseFreq * 4] : [];

  return (
    <div style={{ background: '#0f172a', borderRadius: 10, padding: '16px', border: '1px solid #1e293b' }}>
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', justifyContent: 'space-between' }}>
        <span>Frequency Spectrum (FFT)</span>
        {baseFreq && <span style={{ color: '#a78bfa' }}>f₀ = {baseFreq.toFixed(2)} Hz</span>}
      </div>
      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="specGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.6} />
              <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" stroke='#1e293b' />
          <XAxis dataKey="freq" tick={{ fontSize: 9, fill: '#475569' }} interval={9}
            label={{ value: 'Hz', position: 'insideRight', offset: -5, fill: '#475569', fontSize: 9 }} />
          <YAxis tick={{ fontSize: 9, fill: '#475569' }} />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6, fontSize: 11 }}
            formatter={(v: number) => [`${v.toFixed(4)} mm/s`, 'Amplitude']}
            labelFormatter={(l) => `${l} Hz`}
          />
          {harmonics.map((h, i) => (
            <ReferenceLine key={i} x={h.toFixed(1)}
              stroke={i === 0 ? '#a78bfa' : '#6366f1'} strokeWidth={1.5}
              strokeDasharray={i === 0 ? undefined : "2 3"} />
          ))}
          <Area type="monotone" dataKey="amp" stroke='#a78bfa' fill='url(#specGrad)'
            strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

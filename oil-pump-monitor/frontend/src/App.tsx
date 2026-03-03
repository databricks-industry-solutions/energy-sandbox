import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Waves, MapPin, AlertTriangle, BarChart2, Bot, XCircle, Share2 } from 'lucide-react';
import { LiveMetrics } from './components/LiveMetrics';
import { WaveformChart } from './components/WaveformChart';
import { SpectrumChart } from './components/SpectrumChart';
import { FieldMap } from './components/FieldMap';
import { AlertPanel } from './components/AlertPanel';
import { PumpSelector } from './components/PumpSelector';
import { GenieChat } from './components/GenieChat';
import { DataFlowDiagram } from './components/DataFlowDiagram';
import { useLiveReading, useHistory, useSpectrum, useFieldSummary, useAlerts } from './hooks/useApi';

type Tab = 'dashboard' | 'waveforms' | 'spectrum' | 'field' | 'alerts' | 'genie' | 'dataflow';

interface GenieBanner {
  pumps: string[];
  ts: Date;
}

export default function App() {
  const [selectedPump, setSelectedPump] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [genieBanner, setGenieBanner] = useState<GenieBanner | null>(null);

  const fieldSummary = useFieldSummary(3000);
  const alerts = useAlerts(5000);
  const { reading } = useLiveReading(selectedPump, 2000);
  const history = useHistory(selectedPump, 30, 5000);
  const spectrum = useSpectrum(selectedPump, 5000);

  useEffect(() => {
    if (!selectedPump && fieldSummary.length > 0) {
      setSelectedPump(fieldSummary[0].pump_id);
    }
  }, [fieldSummary, selectedPump]);

  const handleCriticalAlert = useCallback((pumps: string[]) => {
    setGenieBanner({ pumps, ts: new Date() });
    // Auto-dismiss after 12 seconds
    setTimeout(() => setGenieBanner(null), 12000);
  }, []);

  const criticalCount = fieldSummary.filter(p => p.alert_level === 'critical').length;
  const warningCount = fieldSummary.filter(p => p.alert_level === 'warning').length;
  const selectedPumpData = fieldSummary.find(p => p.pump_id === selectedPump);

  const tabs: { id: Tab; label: string; icon: React.ElementType; badge?: number }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: BarChart2 },
    { id: 'waveforms', label: 'Waveforms', icon: Waves },
    { id: 'spectrum', label: 'Spectrum', icon: Activity },
    { id: 'field', label: 'Field Map', icon: MapPin },
    { id: 'alerts', label: 'Alerts', icon: AlertTriangle, badge: alerts.length || undefined },
    { id: 'genie', label: 'Genie AI', icon: Bot },
    { id: 'dataflow', label: 'Data Flow', icon: Share2 },
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#060b18', padding: '0 0 40px 0' }}>
      {/* Header */}
      <div style={{
        background: '#0a0e1a', borderBottom: '1px solid #1e293b',
        padding: '14px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, background: '#1e3a5f', borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '1px solid #38bdf8'
          }}>
            <Waves size={18} color='#38bdf8' />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0' }}>
              Bakken Field Vibration Monitor
            </div>
            <div style={{ fontSize: 11, color: '#64748b' }}>
              North Dakota — Williston Basin Fracking Operations
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {criticalCount > 0 && (
            <div style={{
              background: '#ef444422', border: '1px solid #ef4444',
              borderRadius: 20, padding: '3px 12px', fontSize: 11, color: '#f87171',
              display: 'flex', alignItems: 'center', gap: 5
            }}>
              <AlertTriangle size={10} /> {criticalCount} Critical
            </div>
          )}
          {warningCount > 0 && (
            <div style={{
              background: '#eab30822', border: '1px solid #eab308',
              borderRadius: 20, padding: '3px 12px', fontSize: 11, color: '#facc15',
              display: 'flex', alignItems: 'center', gap: 5
            }}>
              <AlertTriangle size={10} /> {warningCount} Warning
            </div>
          )}
          <div style={{ fontSize: 11, color: '#475569', fontVariantNumeric: 'tabular-nums' }}>
            {new Date().toLocaleTimeString('en-US', { hour12: false })} UTC
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#22c55e' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', animation: 'blink 2s infinite' }} />
            LIVE
          </div>
        </div>
      </div>

      {/* Genie Critical Alert Banner */}
      {genieBanner && (
        <div style={{
          background: '#1a000088', borderBottom: '1px solid #ef4444',
          padding: '10px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          animation: 'slideDown 0.3s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Bot size={14} color='#a78bfa' />
            <span style={{ fontSize: 12, color: '#f87171', fontWeight: 600 }}>
              Genie AI detected critical fault on: {genieBanner.pumps.join(', ')}
            </span>
            <span style={{ fontSize: 11, color: '#64748b' }}>
              at {genieBanner.ts.toLocaleTimeString('en-US', { hour12: false })}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              onClick={() => setActiveTab('genie')}
              style={{
                background: '#4f46e5', border: 'none', borderRadius: 6,
                padding: '4px 12px', cursor: 'pointer', fontSize: 11, color: '#fff'
              }}
            >
              View Analysis
            </button>
            <button
              onClick={() => setGenieBanner(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
            >
              <XCircle size={14} color='#475569' />
            </button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{
        background: '#0a0e1a', borderBottom: '1px solid #1e293b',
        padding: '0 24px', display: 'flex', gap: 0
      }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '10px 16px', fontSize: 12,
              fontWeight: activeTab === tab.id ? 600 : 400,
              color: tab.id === 'genie'
                ? (activeTab === 'genie' ? '#a78bfa' : '#7c3aed')
                : (activeTab === tab.id ? '#38bdf8' : '#64748b'),
              borderBottom: `2px solid ${
                tab.id === 'genie'
                  ? (activeTab === 'genie' ? '#a78bfa' : 'transparent')
                  : (activeTab === tab.id ? '#38bdf8' : 'transparent')
              }`,
              display: 'flex', alignItems: 'center', gap: 5, transition: 'all 0.15s',
              position: 'relative'
            }}
          >
            <tab.icon size={12} />
            {tab.label}
            {tab.badge ? (
              <span style={{
                background: '#ef444422', border: '1px solid #ef4444',
                borderRadius: 10, padding: '0 5px', fontSize: 9, color: '#f87171',
                marginLeft: 2
              }}>
                {tab.badge}
              </span>
            ) : null}
            {tab.id === 'genie' && activeTab !== 'genie' && (
              <span style={{
                width: 5, height: 5, borderRadius: '50%', background: '#7c3aed',
                position: 'absolute', top: 8, right: 8
              }} />
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: activeTab === 'genie' ? '20px 24px' : '20px 24px' }}>

        {/* Pump selector (hidden on genie and dataflow tabs) */}
        {activeTab !== 'genie' && activeTab !== 'dataflow' && (
          <PumpSelector
            pumps={fieldSummary}
            selectedPump={selectedPump}
            onSelect={setSelectedPump}
          />
        )}

        {/* ── Dashboard ── */}
        {activeTab === 'dashboard' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {fieldSummary.map(pump => (
              <LiveMetrics
                key={pump.pump_id}
                reading={pump as any}
                pumpName={pump.name ?? pump.pump_id}
              />
            ))}
          </div>
        )}

        {/* ── Waveforms ── */}
        {activeTab === 'waveforms' && selectedPump && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ fontSize: 13, color: '#64748b', marginBottom: 4 }}>
              Showing last 30 min — {selectedPumpData?.name ?? selectedPump}
            </div>
            <WaveformChart history={history} metric="amplitude_mm_s"
              label="Vibration Amplitude" unit="mm/s" color='#a78bfa'
              warningThreshold={3.5} criticalThreshold={5.0} />
            <WaveformChart history={history} metric="frequency_hz"
              label="Vibration Frequency" unit="Hz" color='#38bdf8' />
            <WaveformChart history={history} metric="rpm"
              label="Pump Speed" unit="RPM" color='#34d399' />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <WaveformChart history={history} metric="temperature_f"
                label="Temperature" unit="°F" color='#f97316'
                warningThreshold={160} criticalThreshold={175} />
              <WaveformChart history={history} metric="pressure_psi"
                label="Wellbore Pressure" unit="PSI" color='#f472b6' />
            </div>
          </div>
        )}

        {/* ── Spectrum ── */}
        {activeTab === 'spectrum' && selectedPump && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ fontSize: 13, color: '#64748b' }}>
              FFT analysis — {selectedPumpData?.name ?? selectedPump}
            </div>
            <SpectrumChart spectrum={spectrum} baseFreq={reading?.frequency_hz} />
            {reading && (
              <div style={{
                background: '#0f172a', borderRadius: 10, padding: 16,
                border: '1px solid #1e293b', display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)', gap: 12
              }}>
                {[
                  { label: 'Fundamental', freq: reading.frequency_hz, color: '#a78bfa' },
                  { label: '2nd Harmonic', freq: reading.frequency_hz * 2, color: '#8b5cf6' },
                  { label: '3rd Harmonic', freq: reading.frequency_hz * 3, color: '#7c3aed' },
                  { label: '4th Harmonic', freq: reading.frequency_hz * 4, color: '#6d28d9' },
                ].map((h, i) => (
                  <div key={i} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{h.label}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: h.color }}>{h.freq.toFixed(2)}</div>
                    <div style={{ fontSize: 10, color: '#475569' }}>Hz</div>
                  </div>
                ))}
              </div>
            )}
            <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>All Pump Summary</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              {fieldSummary.map(p => (
                <div key={p.pump_id} style={{
                  background: '#0f172a', borderRadius: 8, padding: '10px 14px',
                  border: `1px solid ${p.pump_id === selectedPump ? '#38bdf8' : '#1e293b'}`,
                  cursor: 'pointer'
                }} onClick={() => setSelectedPump(p.pump_id)}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#e2e8f0', marginBottom: 6 }}>
                    {p.pump_id.replace('PUMP-ND-', 'P')}
                  </div>
                  <div style={{ fontSize: 10, color: '#64748b', display: 'flex', justifyContent: 'space-between' }}>
                    <span>{(p.frequency_hz as number)?.toFixed(2)} Hz</span>
                    <span>{(p.amplitude_mm_s as number)?.toFixed(2)} mm/s</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Field Map ── */}
        {activeTab === 'field' && (
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
            <FieldMap pumps={fieldSummary} selectedPump={selectedPump} onSelect={setSelectedPump} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {selectedPumpData && (
                <LiveMetrics reading={selectedPumpData as any} pumpName={selectedPumpData.name ?? selectedPump!} />
              )}
              <div style={{ background: '#0f172a', borderRadius: 12, border: '1px solid #1e293b', padding: 16 }}>
                <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>Pump Locations</div>
                {fieldSummary.map(p => (
                  <div key={p.pump_id} onClick={() => setSelectedPump(p.pump_id)}
                    style={{ padding: '8px 0', borderBottom: '1px solid #1e293b', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 12, color: p.pump_id === selectedPump ? '#38bdf8' : '#e2e8f0', fontWeight: p.pump_id === selectedPump ? 600 : 400 }}>{p.pump_id}</div>
                      <div style={{ fontSize: 10, color: '#475569' }}>{p.latitude?.toFixed(3)}°N, {Math.abs(p.longitude)?.toFixed(3)}°W</div>
                    </div>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: p.alert_level === 'critical' ? '#ef4444' : p.alert_level === 'warning' ? '#eab308' : '#22c55e' }} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Alerts ── */}
        {activeTab === 'alerts' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <AlertPanel alerts={alerts} />
            <div style={{ background: '#0f172a', borderRadius: 12, border: '1px solid #1e293b', padding: 16 }}>
              <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>Field Status Overview</div>
              {fieldSummary.map(p => (
                <div key={p.pump_id} style={{ padding: '10px 0', borderBottom: '1px solid #0f172a', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 500 }}>{p.name}</div>
                    <div style={{ fontSize: 10, color: '#64748b' }}>
                      {(p.amplitude_mm_s as number)?.toFixed(2)} mm/s &bull; {p.rpm} RPM &bull; {(p.temperature_f as number)?.toFixed(0)}°F
                    </div>
                  </div>
                  <div style={{
                    fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                    background: p.alert_level === 'critical' ? '#ef444422' : p.alert_level === 'warning' ? '#eab30822' : '#22c55e22',
                    color: p.alert_level === 'critical' ? '#f87171' : p.alert_level === 'warning' ? '#facc15' : '#4ade80',
                    border: `1px solid ${p.alert_level === 'critical' ? '#7f1d1d' : p.alert_level === 'warning' ? '#78350f' : '#166534'}`,
                  }}>
                    {(p.alert_level ?? 'NORMAL').toUpperCase()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Data Flow ── */}
        {activeTab === 'dataflow' && (
          <DataFlowDiagram />
        )}

        {/* ── Genie AI ── */}
        {activeTab === 'genie' && (
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
            <div style={{ background: '#0a0e1a', borderRadius: 12, border: '1px solid #1e1b3a', overflow: 'hidden' }}>
              <GenieChat onCriticalAlert={handleCriticalAlert} />
            </div>
            {/* Right panel: live field context */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ background: '#0f172a', borderRadius: 12, border: '1px solid #1e1b3a', padding: 16 }}>
                <div style={{ fontSize: 12, color: '#7c3aed', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Bot size={11} /> Live Field Context
                </div>
                {fieldSummary.map(p => (
                  <div key={p.pump_id} style={{
                    padding: '8px 0', borderBottom: '1px solid #1e293b',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                  }}>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: '#e2e8f0' }}>{p.pump_id.replace('PUMP-ND-', 'P')}</div>
                      <div style={{ fontSize: 10, color: '#64748b' }}>
                        {(p.amplitude_mm_s as number)?.toFixed(2)} mm/s · {p.rpm} RPM
                      </div>
                    </div>
                    <div style={{
                      fontSize: 9, fontWeight: 700, padding: '2px 7px', borderRadius: 10,
                      background: p.alert_level === 'critical' ? '#ef444422' : p.alert_level === 'warning' ? '#eab30822' : '#22c55e11',
                      color: p.alert_level === 'critical' ? '#f87171' : p.alert_level === 'warning' ? '#facc15' : '#4ade80',
                      border: `1px solid ${p.alert_level === 'critical' ? '#7f1d1d' : p.alert_level === 'warning' ? '#78350f' : '#166534'}`,
                    }}>
                      {(p.alert_level ?? 'OK').toUpperCase()}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ background: '#0f172a', borderRadius: 12, border: '1px solid #1e1b3a', padding: 16 }}>
                <div style={{ fontSize: 12, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>Genie Capabilities</div>
                {[
                  ['Fault Diagnosis', 'Bearing, cavitation, imbalance, overspeed'],
                  ['Trend Analysis', 'Historical pattern detection'],
                  ['Proactive Scan', 'Auto-scans field every 60 seconds'],
                  ['Recommendations', 'Ranked maintenance priorities'],
                  ['Spectrum Analysis', 'Harmonic fault signatures'],
                ].map(([title, desc]) => (
                  <div key={title} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 11, color: '#a78bfa', fontWeight: 600 }}>{title}</div>
                    <div style={{ fontSize: 10, color: '#475569' }}>{desc}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
      `}</style>
    </div>
  );
}

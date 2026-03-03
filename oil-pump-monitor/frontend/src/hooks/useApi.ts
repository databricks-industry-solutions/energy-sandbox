import { useState, useEffect, useCallback, useRef } from 'react';
import type { VibrationReading, SpectrumReading, FieldSummaryItem, PumpStats } from '../types';

const BASE = '/api';

export function useLiveReading(pumpId: string | null, intervalMs = 2000) {
  const [reading, setReading] = useState<VibrationReading | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pumpId) return;
    let cancelled = false;

    const fetch_ = async () => {
      try {
        const r = await fetch(`${BASE}/pumps/${pumpId}/live`);
        if (!cancelled && r.ok) {
          setReading(await r.json());
          setError(null);
        }
      } catch {
        if (!cancelled) setError('Connection error');
      }
    };

    fetch_();
    const id = setInterval(fetch_, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [pumpId, intervalMs]);

  return { reading, error };
}

export function useHistory(pumpId: string | null, minutes = 30, intervalMs = 5000) {
  const [history, setHistory] = useState<VibrationReading[]>([]);

  useEffect(() => {
    if (!pumpId) return;
    let cancelled = false;

    const fetch_ = async () => {
      try {
        const r = await fetch(`${BASE}/pumps/${pumpId}/history?minutes=${minutes}`);
        if (!cancelled && r.ok) setHistory(await r.json());
      } catch { /* ignore */ }
    };

    fetch_();
    const id = setInterval(fetch_, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [pumpId, minutes, intervalMs]);

  return history;
}

export function useSpectrum(pumpId: string | null, intervalMs = 5000) {
  const [spectrum, setSpectrum] = useState<SpectrumReading | null>(null);

  useEffect(() => {
    if (!pumpId) return;
    let cancelled = false;

    const fetch_ = async () => {
      try {
        const r = await fetch(`${BASE}/pumps/${pumpId}/spectrum`);
        if (!cancelled && r.ok) setSpectrum(await r.json());
      } catch { /* ignore */ }
    };

    fetch_();
    const id = setInterval(fetch_, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [pumpId, intervalMs]);

  return spectrum;
}

export function useFieldSummary(intervalMs = 3000) {
  const [summary, setSummary] = useState<FieldSummaryItem[]>([]);

  useEffect(() => {
    let cancelled = false;

    const fetch_ = async () => {
      try {
        const r = await fetch(`${BASE}/field/summary`);
        if (!cancelled && r.ok) setSummary(await r.json());
      } catch { /* ignore */ }
    };

    fetch_();
    const id = setInterval(fetch_, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [intervalMs]);

  return summary;
}

export function usePumpStats(pumpId: string | null) {
  const [stats, setStats] = useState<PumpStats | null>(null);

  useEffect(() => {
    if (!pumpId) return;
    fetch(`${BASE}/pumps/${pumpId}/stats`)
      .then(r => r.json())
      .then(setStats)
      .catch(() => {});
  }, [pumpId]);

  return stats;
}

export function useAlerts(intervalMs = 5000) {
  const [alerts, setAlerts] = useState<(VibrationReading & { pump_name: string })[]>([]);

  useEffect(() => {
    let cancelled = false;

    const fetch_ = async () => {
      try {
        const r = await fetch(`${BASE}/alerts?limit=15`);
        if (!cancelled && r.ok) setAlerts(await r.json());
      } catch { /* ignore */ }
    };

    fetch_();
    const id = setInterval(fetch_, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [intervalMs]);

  return alerts;
}

export interface Pump {
  pump_id: string;
  name: string;
  latitude: number;
  longitude: number;
  field_section: string;
  status: string;
}

export interface VibrationReading {
  pump_id: string;
  timestamp: string;
  frequency_hz: number;
  amplitude_mm_s: number;
  rpm: number;
  temperature_f: number;
  pressure_psi: number;
  is_anomaly: boolean;
  alert_level: 'normal' | 'warning' | 'critical';
}

export interface SpectrumReading {
  pump_id: string;
  timestamp: string;
  frequencies: number[];
  amplitudes: number[];
}

export interface FieldSummaryItem extends VibrationReading {
  name: string;
  latitude: number;
  longitude: number;
  last_reading: string;
}

export interface PumpStats {
  total_readings: number;
  avg_frequency: number;
  avg_amplitude: number;
  max_amplitude: number;
  avg_rpm: number;
  avg_temperature: number;
  avg_pressure: number;
  anomaly_count: number;
  critical_count: number;
}

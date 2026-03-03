"""
Realistic oil pump vibration simulator for North Dakota Bakken Formation.
Generates soundwave data with harmonics, noise, and anomaly injection.
"""

import math
import random
import asyncio
import numpy as np
from datetime import datetime
from typing import Optional

# Pump operational profiles (Bakken formation typical parameters)
PUMP_PROFILES = {
    "PUMP-ND-001": {"base_rpm": 280, "base_freq": 4.67, "base_amp": 2.1, "base_temp": 145.0, "base_psi": 2850},
    "PUMP-ND-002": {"base_rpm": 320, "base_freq": 5.33, "base_amp": 1.8, "base_temp": 138.0, "base_psi": 3100},
    "PUMP-ND-003": {"base_rpm": 295, "base_freq": 4.92, "base_amp": 2.4, "base_temp": 152.0, "base_psi": 2950},
    "PUMP-ND-004": {"base_rpm": 310, "base_freq": 5.17, "base_amp": 1.9, "base_temp": 141.0, "base_psi": 3050},
    "PUMP-ND-005": {"base_rpm": 275, "base_freq": 4.58, "base_amp": 2.2, "base_temp": 149.0, "base_psi": 2800},
    "PUMP-ND-006": {"base_rpm": 305, "base_freq": 5.08, "base_amp": 2.0, "base_temp": 143.0, "base_psi": 3000},
}

# Anomaly probability per reading (3% chance)
ANOMALY_PROB = 0.03

def generate_vibration_reading(pump_id: str) -> dict:
    """Generate a realistic vibration reading with soundwave simulation."""
    profile = PUMP_PROFILES.get(pump_id, PUMP_PROFILES["PUMP-ND-001"])
    now = datetime.utcnow()

    # Time-based drift (simulates diurnal temperature/pressure variation)
    hour_factor = math.sin(now.hour * math.pi / 12) * 0.05

    # Random walk noise
    rpm_jitter = random.gauss(0, 3)
    rpm = max(200, min(400, profile["base_rpm"] + rpm_jitter + profile["base_rpm"] * hour_factor))

    # Fundamental frequency from RPM
    freq_hz = rpm / 60.0 + random.gauss(0, 0.05)

    # Amplitude with harmonics (2x, 3x, 4x) and bearing wear noise
    amp_base = profile["base_amp"]
    amp_noise = random.gauss(0, 0.12)
    amplitude = max(0.1, amp_base + amp_noise + amp_base * hour_factor * 0.3)

    # Temperature (Fahrenheit) - rises with high RPM
    temp = profile["base_temp"] + (rpm - profile["base_rpm"]) * 0.08 + random.gauss(0, 1.5)

    # Pressure (PSI)
    pressure = profile["base_psi"] + random.gauss(0, 25) + (rpm - profile["base_rpm"]) * 0.5

    # Anomaly injection
    is_anomaly = random.random() < ANOMALY_PROB
    alert_level = "normal"

    if is_anomaly:
        anomaly_type = random.choice(["bearing_fault", "cavitation", "imbalance", "overspeed"])
        if anomaly_type == "bearing_fault":
            amplitude *= random.uniform(2.5, 4.0)
            freq_hz *= random.uniform(1.8, 2.2)
            alert_level = "critical"
        elif anomaly_type == "cavitation":
            amplitude *= random.uniform(1.5, 2.5)
            pressure -= random.uniform(200, 500)
            alert_level = "warning"
        elif anomaly_type == "imbalance":
            amplitude *= random.uniform(1.3, 2.0)
            rpm += random.uniform(30, 60)
            alert_level = "warning"
        elif anomaly_type == "overspeed":
            rpm = min(450, rpm * random.uniform(1.2, 1.4))
            freq_hz = rpm / 60.0
            amplitude *= random.uniform(1.4, 1.8)
            temp += random.uniform(10, 25)
            alert_level = "critical"

    # Additional warning threshold check
    if alert_level == "normal":
        if amplitude > profile["base_amp"] * 1.8:
            alert_level = "warning"
        if temp > profile["base_temp"] + 20:
            alert_level = "warning"

    return {
        "pump_id": pump_id,
        "timestamp": now,
        "frequency_hz": round(freq_hz, 3),
        "amplitude_mm_s": round(amplitude, 4),
        "rpm": int(rpm),
        "temperature_f": round(temp, 2),
        "pressure_psi": round(pressure, 1),
        "is_anomaly": is_anomaly,
        "alert_level": alert_level,
    }

def generate_spectrum(pump_id: str) -> dict:
    """Generate frequency spectrum data (FFT-like output) for a pump."""
    profile = PUMP_PROFILES.get(pump_id, PUMP_PROFILES["PUMP-ND-001"])
    base_freq = profile["base_freq"]

    # Frequency bins: 0 to 50 Hz in 0.5 Hz steps
    freqs = np.arange(0, 50.5, 0.5).tolist()
    amps = []

    for f in freqs:
        amp = 0.0
        # Fundamental
        amp += profile["base_amp"] * 0.8 * _gaussian(f, base_freq, 0.3)
        # 2nd harmonic
        amp += profile["base_amp"] * 0.4 * _gaussian(f, base_freq * 2, 0.4)
        # 3rd harmonic
        amp += profile["base_amp"] * 0.2 * _gaussian(f, base_freq * 3, 0.5)
        # 4th harmonic
        amp += profile["base_amp"] * 0.1 * _gaussian(f, base_freq * 4, 0.6)
        # White noise floor
        amp += abs(random.gauss(0, 0.05))
        amps.append(round(amp, 4))

    return {
        "pump_id": pump_id,
        "timestamp": datetime.utcnow(),
        "frequencies": freqs,
        "amplitudes": amps,
    }

def _gaussian(x: float, mu: float, sigma: float) -> float:
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


class PumpSimulator:
    """Background task that continuously writes simulated data to Lakebase."""

    def __init__(self, db, interval_seconds: float = 2.0):
        self.db = db
        self.interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run())
        print("Pump simulator started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _run(self):
        spectrum_counter = 0
        while self._running:
            try:
                for pump_id in PUMP_PROFILES.keys():
                    reading = generate_vibration_reading(pump_id)
                    await self.db.execute(
                        """INSERT INTO vibration_readings
                           (pump_id, timestamp, frequency_hz, amplitude_mm_s, rpm,
                            temperature_f, pressure_psi, is_anomaly, alert_level)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                        reading["pump_id"], reading["timestamp"],
                        reading["frequency_hz"], reading["amplitude_mm_s"],
                        reading["rpm"], reading["temperature_f"],
                        reading["pressure_psi"], reading["is_anomaly"],
                        reading["alert_level"]
                    )

                # Generate spectrum every 10 cycles (20 seconds)
                if spectrum_counter % 10 == 0:
                    for pump_id in PUMP_PROFILES.keys():
                        spec = generate_spectrum(pump_id)
                        await self.db.execute(
                            """INSERT INTO spectrum_readings
                               (pump_id, timestamp, frequencies, amplitudes)
                               VALUES ($1, $2, $3::double precision[], $4::double precision[])""",
                            spec["pump_id"], spec["timestamp"],
                            spec["frequencies"], spec["amplitudes"]
                        )

                spectrum_counter += 1
                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Simulator error: {e}")
                await asyncio.sleep(5)

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timedelta
from ..db import db
from ..simulator import generate_vibration_reading, generate_spectrum, PUMP_PROFILES

router = APIRouter()

@router.get("/pumps")
async def get_pumps():
    """Get all pump definitions with locations."""
    rows = await db.fetch("SELECT * FROM pumps ORDER BY pump_id")
    if not rows:
        # Demo mode fallback
        return [
            {"pump_id": pid, "name": f"Bakken Unit {i+1}", "status": "active",
             "latitude": 47.8 + i*0.1, "longitude": -103.5 + i*0.2,
             "field_section": "Section A"}
            for i, pid in enumerate(PUMP_PROFILES.keys())
        ]
    return [dict(r) for r in rows]

@router.get("/pumps/{pump_id}/live")
async def get_live_reading(pump_id: str):
    """Get the latest vibration reading for a pump."""
    row = await db.fetchrow(
        """SELECT * FROM vibration_readings
           WHERE pump_id = $1
           ORDER BY timestamp DESC LIMIT 1""",
        pump_id
    )
    if row:
        return dict(row)
    # Generate live data if DB has nothing yet
    return generate_vibration_reading(pump_id)

@router.get("/pumps/{pump_id}/history")
async def get_history(
    pump_id: str,
    minutes: int = Query(default=30, ge=1, le=1440)
):
    """Get historical vibration readings for a pump."""
    since = datetime.utcnow() - timedelta(minutes=minutes)
    rows = await db.fetch(
        """SELECT timestamp, frequency_hz, amplitude_mm_s, rpm,
                  temperature_f, pressure_psi, is_anomaly, alert_level
           FROM vibration_readings
           WHERE pump_id = $1 AND timestamp >= $2
           ORDER BY timestamp ASC""",
        pump_id, since
    )
    if rows:
        return [dict(r) for r in rows]
    # Demo fallback: generate synthetic history
    result = []
    now = datetime.utcnow()
    for i in range(min(minutes * 30, 500)):
        r = generate_vibration_reading(pump_id)
        r["timestamp"] = (now - timedelta(seconds=(minutes*60 - i*2))).isoformat()
        result.append(r)
    return result

@router.get("/pumps/{pump_id}/spectrum")
async def get_spectrum(pump_id: str):
    """Get the latest frequency spectrum for a pump."""
    row = await db.fetchrow(
        """SELECT * FROM spectrum_readings
           WHERE pump_id = $1
           ORDER BY timestamp DESC LIMIT 1""",
        pump_id
    )
    if row:
        return dict(row)
    return generate_spectrum(pump_id)

@router.get("/pumps/{pump_id}/stats")
async def get_stats(pump_id: str):
    """Get aggregated statistics for a pump."""
    row = await db.fetchrow(
        """SELECT
            COUNT(*) as total_readings,
            AVG(frequency_hz) as avg_frequency,
            AVG(amplitude_mm_s) as avg_amplitude,
            MAX(amplitude_mm_s) as max_amplitude,
            AVG(rpm) as avg_rpm,
            AVG(temperature_f) as avg_temperature,
            AVG(pressure_psi) as avg_pressure,
            SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) as anomaly_count,
            SUM(CASE WHEN alert_level = 'critical' THEN 1 ELSE 0 END) as critical_count
           FROM vibration_readings
           WHERE pump_id = $1
             AND timestamp >= NOW() - INTERVAL '1 hour'""",
        pump_id
    )
    if row:
        return dict(row)
    profile = PUMP_PROFILES.get(pump_id, {})
    return {
        "total_readings": 0,
        "avg_frequency": profile.get("base_freq", 5.0),
        "avg_amplitude": profile.get("base_amp", 2.0),
        "max_amplitude": profile.get("base_amp", 2.0) * 1.1,
        "avg_rpm": profile.get("base_rpm", 300),
        "avg_temperature": profile.get("base_temp", 145),
        "avg_pressure": profile.get("base_psi", 3000),
        "anomaly_count": 0,
        "critical_count": 0,
    }

@router.get("/alerts")
async def get_recent_alerts(limit: int = Query(default=20, le=100)):
    """Get recent anomaly alerts across all pumps."""
    rows = await db.fetch(
        """SELECT vr.*, p.name as pump_name
           FROM vibration_readings vr
           JOIN pumps p ON p.pump_id = vr.pump_id
           WHERE vr.alert_level != 'normal'
           ORDER BY vr.timestamp DESC
           LIMIT $1""",
        limit
    )
    if rows:
        return [dict(r) for r in rows]
    return []

@router.get("/field/summary")
async def get_field_summary():
    """Get summary statistics across the entire field."""
    rows = await db.fetch(
        """SELECT
            p.pump_id,
            p.name,
            p.latitude,
            p.longitude,
            p.status,
            latest.frequency_hz,
            latest.amplitude_mm_s,
            latest.rpm,
            latest.temperature_f,
            latest.pressure_psi,
            latest.alert_level,
            latest.timestamp as last_reading
           FROM pumps p
           LEFT JOIN LATERAL (
               SELECT frequency_hz, amplitude_mm_s, rpm, temperature_f,
                      pressure_psi, alert_level, timestamp
               FROM vibration_readings
               WHERE pump_id = p.pump_id
               ORDER BY timestamp DESC
               LIMIT 1
           ) latest ON true
           ORDER BY p.pump_id"""
    )
    if rows:
        return [dict(r) for r in rows]
    # Demo fallback
    result = []
    for pump_id, profile in PUMP_PROFILES.items():
        r = generate_vibration_reading(pump_id)
        result.append({
            "pump_id": pump_id,
            "name": f"Bakken Unit {list(PUMP_PROFILES.keys()).index(pump_id)+1}",
            "latitude": 47.8 + list(PUMP_PROFILES.keys()).index(pump_id) * 0.1,
            "longitude": -103.5 + list(PUMP_PROFILES.keys()).index(pump_id) * 0.2,
            "status": "active",
            **r,
        })
    return result

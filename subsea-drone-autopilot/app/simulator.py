"""
Subsea Fleet Simulator – physics-based telemetry generation for 5 ROV/AUVs.

Like ESP PM's simulator: sinusoidal base + fault injection + event cycles.
Each drone has a personality (different fault profiles).
"""

import math
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Drone Profiles ──────────────────────────────────────────

DRONE_PROFILES = {
    "DRONE-01": {
        "name": "Triton-1A", "model": "Subsea Explorer 500",
        "fault_mode": "healthy", "base_depth": 0, "field": "Block 42",
        "thruster_bias": [0.0, 0.0, 0.0, 0.0],
    },
    "DRONE-02": {
        "name": "Poseidon-2B", "model": "Subsea Explorer 500",
        "fault_mode": "thruster_wear", "base_depth": 155, "field": "Block 42",
        "thruster_bias": [0.0, 0.8, 0.0, 0.3],  # port-bottom thruster wearing
    },
    "DRONE-03": {
        "name": "Neptune-3C", "model": "Subsea Explorer 300",
        "fault_mode": "battery_degradation", "base_depth": 0, "field": "Campos Basin",
        "thruster_bias": [0.0, 0.0, 0.0, 0.0],
    },
    "DRONE-04": {
        "name": "Nereus-4D", "model": "Subsea Explorer 500",
        "fault_mode": "healthy", "base_depth": 0, "field": "Block 42",
        "thruster_bias": [0.0, 0.0, 0.0, 0.0],
    },
    "DRONE-05": {
        "name": "Kraken-5E", "model": "Subsea Explorer 1000",
        "fault_mode": "sensor_drift", "base_depth": 0, "field": "Campos Basin",
        "thruster_bias": [0.0, 0.0, 0.2, 0.0],
    },
}

# ── Mission Templates ───────────────────────────────────────

ACTIVE_MISSIONS = {
    "DRONE-02": {
        "mission_id": "MIS-DEMO-004",
        "asset_id": "Manifold-B2",
        "asset_type": "manifold",
        "target_depth": 165,
        "risk_level": "medium",
        "start_tick": 0,
        "duration_ticks": 200,
    },
}

# ── Environment ─────────────────────────────────────────────

@dataclass
class Environment:
    sea_state: str = "moderate"
    wave_height_m: float = 1.2
    current_speed_knots: float = 0.8
    current_direction_deg: float = 225.0
    visibility_m: float = 8.5
    water_temp_c: float = 5.8
    salinity_ppt: float = 35.2
    weather: str = "partly_cloudy"

    def update(self, tick: int):
        t = tick * 0.05
        self.wave_height_m = round(1.0 + 0.8 * abs(math.sin(t * 0.1)), 1)
        self.current_speed_knots = round(0.5 + 0.6 * abs(math.sin(t * 0.07 + 1)), 2)
        self.current_direction_deg = round((225 + math.sin(t * 0.03) * 30) % 360, 1)
        self.visibility_m = round(8 + math.sin(t * 0.12) * 4, 1)
        self.water_temp_c = round(5.5 + math.sin(t * 0.08) * 1.5, 1)

        if self.wave_height_m < 0.8:
            self.sea_state = "calm"
        elif self.wave_height_m < 1.8:
            self.sea_state = "moderate"
        else:
            self.sea_state = "rough"


# ── Telemetry Point ─────────────────────────────────────────

@dataclass
class TelemetryPoint:
    drone_id: str
    depth_m: float
    imu_roll_deg: float
    imu_pitch_deg: float
    imu_yaw_deg: float
    thruster_currents: list[float]
    internal_temps_c: list[float]
    network_rssi_dbm: float
    nav_error_m: float
    battery_pct: float
    battery_draw_w: float
    propulsion_rpm: list[int]
    health_score: float
    anomaly_score: float
    state: str
    mission_id: Optional[str]


# ── Simulator ───────────────────────────────────────────────

class FleetSimulator:
    def __init__(self):
        self.tick = 0
        self.env = Environment()
        self._rng = random.Random(42)

        # Per-drone state
        self._battery = {
            "DRONE-01": 92.0, "DRONE-02": 72.0, "DRONE-03": 45.0,
            "DRONE-04": 85.0, "DRONE-05": 60.0,
        }
        self._states = {
            "DRONE-01": "idle", "DRONE-02": "in_mission", "DRONE-03": "maintenance",
            "DRONE-04": "idle", "DRONE-05": "cooldown",
        }
        self._health = {
            "DRONE-01": 0.95, "DRONE-02": 0.88, "DRONE-03": 0.72,
            "DRONE-04": 0.91, "DRONE-05": 0.83,
        }
        self._maintenance = {"DRONE-03": True}

    def step(self) -> dict[str, TelemetryPoint]:
        """Advance one tick and return telemetry for all drones."""
        self.tick += 1
        self.env.update(self.tick)
        result = {}

        for drone_id, profile in DRONE_PROFILES.items():
            result[drone_id] = self._simulate_drone(drone_id, profile)

        return result

    def _simulate_drone(self, drone_id: str, profile: dict) -> TelemetryPoint:
        t = self.tick * 0.1
        s = math.sin
        c = math.cos
        idx = int(drone_id[-1])
        state = self._states.get(drone_id, "idle")
        is_active = state == "in_mission"
        fault = profile["fault_mode"]
        mission = ACTIVE_MISSIONS.get(drone_id)

        # ── Depth ──
        if is_active and mission:
            target = mission["target_depth"]
            phase = (self.tick - mission["start_tick"]) / max(1, mission["duration_ticks"])
            if phase < 0.1:
                depth = target * phase * 10  # descending
            elif phase > 0.9:
                depth = target * (1 - (phase - 0.9) * 10)  # ascending
            else:
                depth = target + s(t * 0.3) * 15 + self._rng.uniform(-2, 2)
        else:
            depth = profile["base_depth"]

        # ── IMU ──
        wave_effect = self.env.wave_height_m * 0.5
        roll = s(t * 1.2 + idx) * (2 + wave_effect) + (s(t * 3) * 1.5 if is_active else 0)
        pitch = c(t * 0.8 + idx) * (1.5 + wave_effect) + (c(t * 2.5) * 1.0 if is_active else 0)
        yaw = 180 + s(t * 0.2) * 20 + self.env.current_direction_deg * 0.05

        # ── Thrusters ──
        base_current = 2.5 if is_active else 0.1
        bias = profile["thruster_bias"]
        currents = [
            round(base_current + s(t + i) * 0.8 + bias[i] + (0.5 if fault == "thruster_wear" and i == 1 else 0), 2)
            for i in range(4)
        ]

        # Fault: thruster imbalance
        if fault == "thruster_wear" and is_active:
            currents[1] += abs(s(t * 0.5)) * 1.2  # progressive wear
            currents[1] = round(currents[1], 2)

        # ── Temperatures ──
        base_temp = 30 + idx * 1.5
        temps = [
            round(base_temp + s(t * 0.5 + i) * 2 + (8 if is_active else 0) +
                  (3 if fault == "thruster_wear" else 0), 1)
            for i in range(3)
        ]

        # ── Comms ──
        rssi = -48 - abs(s(t * 0.4)) * 20 - (depth * 0.08 if is_active else 0)
        if fault == "sensor_drift":
            rssi -= abs(s(t * 0.2)) * 8

        # ── Nav error ──
        nav_err = 0.2 + abs(s(t * 1.5)) * 0.5 + (0.3 if is_active else 0)
        if fault == "sensor_drift":
            nav_err += 0.5 + abs(s(t * 0.3)) * 1.0  # IMU drift

        # ── Battery ──
        if is_active:
            drain = 0.015 + abs(s(t)) * 0.005
            self._battery[drone_id] = max(5, self._battery[drone_id] - drain)
        elif state == "cooldown":
            self._battery[drone_id] = min(100, self._battery[drone_id] + 0.005)  # slow charge

        battery_draw = 120 + s(t * 2) * 30 if is_active else 5
        if fault == "battery_degradation":
            battery_draw *= 1.3

        # ── RPM ──
        rpm = [round(1200 + s(t * 2 + i) * 300) if is_active else 0 for i in range(4)]

        # ── Health & Anomaly ──
        anomaly = 0.05 + abs(s(t * 0.3)) * 0.1
        if fault == "thruster_wear" and is_active:
            anomaly += 0.25 + abs(s(t * 0.2)) * 0.15
        if fault == "sensor_drift":
            anomaly += 0.15
        if fault == "battery_degradation":
            anomaly += 0.10
        anomaly = min(1.0, anomaly)

        health = self._health[drone_id]
        if anomaly > 0.4:
            health = max(0.5, health - 0.001)
        self._health[drone_id] = health

        return TelemetryPoint(
            drone_id=drone_id,
            depth_m=round(max(0, depth), 1),
            imu_roll_deg=round(roll, 1),
            imu_pitch_deg=round(pitch, 1),
            imu_yaw_deg=round(yaw % 360, 1),
            thruster_currents=[round(c, 2) for c in currents],
            internal_temps_c=temps,
            network_rssi_dbm=round(rssi),
            nav_error_m=round(max(0, nav_err), 2),
            battery_pct=round(self._battery[drone_id], 1),
            battery_draw_w=round(battery_draw, 1),
            propulsion_rpm=rpm,
            health_score=round(health, 3),
            anomaly_score=round(anomaly, 3),
            state=state,
            mission_id=ACTIVE_MISSIONS.get(drone_id, {}).get("mission_id"),
        )

    def get_fleet_summary(self) -> dict:
        """Return fleet-level KPIs."""
        telem = self.step()
        drones = list(telem.values())

        operational = sum(1 for d in drones if d.state in ("idle", "in_mission", "cooldown"))
        in_mission = sum(1 for d in drones if d.state == "in_mission")
        grounded = sum(1 for d in drones if d.state == "maintenance")

        return {
            "tick": self.tick,
            "environment": asdict(self.env),
            "fleet": {
                "total": 5,
                "operational": operational,
                "in_mission": in_mission,
                "grounded": grounded,
                "avg_health": round(sum(d.health_score for d in drones) / 5, 3),
                "avg_battery": round(sum(d.battery_pct for d in drones) / 5, 1),
                "total_anomalies": sum(1 for d in drones if d.anomaly_score > 0.3),
            },
            "drones": {d.drone_id: asdict(d) for d in drones},
        }

    def get_drone_profile(self, drone_id: str) -> dict:
        """Return static profile + current telemetry for a drone."""
        profile = DRONE_PROFILES.get(drone_id, {})
        telem = self._simulate_drone(drone_id, profile)
        return {**profile, **asdict(telem)}


# Singleton
_sim: FleetSimulator | None = None

def get_simulator() -> FleetSimulator:
    global _sim
    if _sim is None:
        _sim = FleetSimulator()
    return _sim

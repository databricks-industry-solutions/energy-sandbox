"""Tests for the BOP stack simulator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.simulator import (
    simulate_tick, get_telemetry_history, get_events, get_anomalies,
    COMPONENTS, SENSOR_DEFS, DRILLING_OPS,
)


class TestSimulateTick:
    def test_returns_required_keys(self):
        state = simulate_tick()
        for key in ("rig_id", "rig_name", "tick", "ts", "status",
                     "components", "readings", "events", "anomalies",
                     "current_op", "kpis"):
            assert key in state, f"Missing key: {key}"

    def test_all_components_present(self):
        state = simulate_tick()
        expected_ids = {c["asset_id"] for c in COMPONENTS}
        assert set(state["components"].keys()) == expected_ids

    def test_component_health_fields(self):
        state = simulate_tick()
        for aid, comp in state["components"].items():
            assert "health_score" in comp
            assert "anomaly_flag" in comp
            assert "component_type" in comp
            assert 0.0 <= comp["health_score"] <= 1.0

    def test_kpis_structure(self):
        state = simulate_tick()
        kpis = state["kpis"]
        assert kpis["total_components"] == len(COMPONENTS)
        assert 0 <= kpis["healthy_components"] <= kpis["total_components"]
        assert 0 <= kpis["active_anomalies"] <= kpis["total_components"]
        assert kpis["depth_md"] > 0
        assert kpis["depth_tvd"] > 0

    def test_rig_status_valid(self):
        state = simulate_tick()
        assert state["status"] in ("NORMAL", "WATCH", "ACT_NOW")

    def test_readings_have_required_fields(self):
        state = simulate_tick()
        for r in state["readings"]:
            assert "asset_id" in r
            assert "tag" in r
            assert "value" in r
            assert "unit" in r
            assert r["value"] >= 0

    def test_current_op_fields(self):
        state = simulate_tick()
        op = state["current_op"]
        assert "op_code" in op
        assert "description" in op
        assert "is_low_risk" in op
        assert "depth_md" in op

    def test_tick_increments(self):
        t1 = simulate_tick()["tick"]
        t2 = simulate_tick()["tick"]
        assert t2 == t1 + 1


class TestAnomalyCycle:
    """Run through a full 40-tick cycle and verify anomalies appear."""

    def test_anomalies_appear_during_cycle(self):
        anomaly_types_seen = set()
        for _ in range(45):
            state = simulate_tick()
            for comp in state["components"].values():
                if comp["anomaly_flag"] and comp.get("anomaly_type"):
                    anomaly_types_seen.add(comp["anomaly_type"])

        expected = {"PRESSURE_LEAK", "COMM_LOSS", "HIGH_CURRENT",
                    "SLOW_CLOSE", "PRESSURE_DECAY"}
        assert anomaly_types_seen == expected, (
            f"Missing anomaly types: {expected - anomaly_types_seen}")


class TestTelemetryHistory:
    def test_history_accumulates(self):
        simulate_tick()
        history = get_telemetry_history()
        assert len(history) > 0

    def test_filter_by_asset(self):
        simulate_tick()
        history = get_telemetry_history(asset_id="BOP-ANN-01")
        assert all(r["asset_id"] == "BOP-ANN-01" for r in history)

    def test_filter_by_tag(self):
        simulate_tick()
        history = get_telemetry_history(tag="ANN_CLOSE_PRESS")
        assert all(r["tag"] == "ANN_CLOSE_PRESS" for r in history)


class TestSensorDefs:
    def test_all_component_types_have_sensors(self):
        ctypes = {c["component_type"] for c in COMPONENTS}
        # PUMP covers both PMP-01 and PMP-02; POD_A/POD_B are separate
        for ctype in ctypes:
            assert ctype in SENSOR_DEFS, f"No sensor defs for {ctype}"

    def test_sensor_defs_have_required_fields(self):
        for ctype, defs in SENSOR_DEFS.items():
            assert len(defs) > 0, f"{ctype} has no sensors"
            for d in defs:
                assert "tag" in d
                assert "base" in d
                assert "unit" in d


class TestDrillingOps:
    def test_ops_not_empty(self):
        assert len(DRILLING_OPS) > 0

    def test_ops_have_required_fields(self):
        for op in DRILLING_OPS:
            assert "op_code" in op
            assert "description" in op
            assert "is_low_risk" in op

"""Tests for mock data integrity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.mock_data import (
    RUL_PREDICTIONS, FAILURE_PATTERNS, SAP_WORK_ORDERS, SAP_SPARES,
    CREW, INTERVENTION_ETA,
    get_qualified_bop_crew, get_intervention_eta, get_spares_for_component,
    get_wo_for_equipment, get_sap_kpis,
)
from app.simulator import COMPONENTS


class TestRulPredictions:
    def test_all_components_have_rul(self):
        rul_ids = {r["asset_id"] for r in RUL_PREDICTIONS}
        comp_ids = {c["asset_id"] for c in COMPONENTS}
        assert rul_ids == comp_ids

    def test_rul_values_positive(self):
        for r in RUL_PREDICTIONS:
            assert r["predicted_rul_days"] > 0
            assert 0 <= r["failure_prob_7d"] <= 1
            assert 0 <= r["failure_prob_30d"] <= 1
            assert r["failure_prob_7d"] <= r["failure_prob_30d"]

    def test_rul_has_model_version(self):
        for r in RUL_PREDICTIONS:
            assert "model_version" in r
            assert len(r["model_version"]) > 0


class TestFailurePatterns:
    def test_patterns_not_empty(self):
        assert len(FAILURE_PATTERNS) > 0

    def test_pattern_fields(self):
        for fp in FAILURE_PATTERNS:
            assert "component_type" in fp
            assert "anomaly_pattern" in fp
            assert "failure_mode" in fp
            assert "fix_action" in fp
            assert fp["avg_ttf_days"] > 0


class TestSapWorkOrders:
    def test_wo_not_empty(self):
        assert len(SAP_WORK_ORDERS) > 0

    def test_wo_fields(self):
        for wo in SAP_WORK_ORDERS:
            assert "wo_id" in wo
            assert "equipment_id" in wo
            assert "status" in wo
            assert wo["status"] in ("OPEN", "IN_PROGRESS", "PLANNED", "COMPLETED")
            assert 1 <= wo["priority"] <= 5

    def test_get_wo_for_equipment(self):
        wos = get_wo_for_equipment("BOP-BSR-01")
        assert len(wos) > 0
        assert all(w["equipment_id"] == "BOP-BSR-01" for w in wos)

    def test_get_wo_nonexistent(self):
        wos = get_wo_for_equipment("NONEXISTENT")
        assert wos == []


class TestSapSpares:
    def test_spares_not_empty(self):
        assert len(SAP_SPARES) > 0

    def test_spares_fields(self):
        for s in SAP_SPARES:
            assert "material_id" in s
            assert "description" in s
            assert "available_qty" in s
            assert s["available_qty"] >= 0
            assert s["min_stock"] >= 0
            assert s["lead_time_days"] > 0
            assert s["unit_price"] > 0

    def test_get_spares_for_component(self):
        spares = get_spares_for_component("ANNULAR")
        assert len(spares) > 0
        assert all(s["component_type"] == "ANNULAR" for s in spares)

    def test_get_spares_unknown_type(self):
        spares = get_spares_for_component("NONEXISTENT")
        assert spares == []


class TestCrew:
    def test_crew_not_empty(self):
        assert len(CREW) > 0

    def test_crew_fields(self):
        for c in CREW:
            assert "crew_id" in c
            assert "name" in c
            assert "role" in c
            assert "shift" in c
            assert c["shift"] in ("Day", "Night")
            assert "zone" in c
            assert "certs" in c
            assert isinstance(c["certs"], list)

    def test_qualified_bop_crew(self):
        qualified = get_qualified_bop_crew()
        assert len(qualified) > 0
        assert len(qualified) <= len(CREW)

    def test_intervention_eta(self):
        for c in CREW:
            eta = get_intervention_eta(c)
            assert eta >= 0
            assert isinstance(eta, int)

    def test_all_zones_have_eta(self):
        zones = {c["zone"] for c in CREW}
        for zone in zones:
            assert zone in INTERVENTION_ETA


class TestSapKpis:
    def test_kpi_fields(self):
        kpis = get_sap_kpis()
        assert "open_wos" in kpis
        assert "critical_wos" in kpis
        assert "total_inventory_value" in kpis
        assert "low_stock_items" in kpis
        assert "crew_on_rig" in kpis
        assert "bop_qualified_crew" in kpis

    def test_kpi_values_reasonable(self):
        kpis = get_sap_kpis()
        assert kpis["open_wos"] >= 0
        assert kpis["total_inventory_value"] > 0
        assert kpis["crew_on_rig"] > 0

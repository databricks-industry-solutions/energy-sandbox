from connector.domains.normalize import get_by_path, max_watermark_from_records, normalize_record
from connector.domains.registry import load_domain_config
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_get_by_path():
    d = {"a": {"b": 1}}
    assert get_by_path(d, "a.b") == 1
    assert get_by_path(d, "a.c") is None


def test_normalize_record():
    cfg = load_domain_config(ROOT / "conf" / "domains" / "wellbore.yaml")
    raw = {
        "id": "rid-1",
        "kind": "k",
        "data": {"modifyTime": "2020-01-01", "FacilityName": "F1", "CountryID": "NO"},
    }
    row = normalize_record(raw, cfg)
    assert row["record_id"] == "rid-1"
    assert row["name"] == "F1"
    assert row["country"] == "NO"


def test_max_watermark():
    recs = [{"data": {"modifyTime": "2020-01-02"}}, {"data": {"modifyTime": "2020-01-03"}}]
    assert max_watermark_from_records(recs, "data.modifyTime") == "2020-01-03"

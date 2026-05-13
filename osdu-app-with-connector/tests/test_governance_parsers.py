from connector.governance.parsers import parse_entitlements_groups_json, parse_legal_tags_json


def test_parse_legal_tags_wrapped():
    body = {"legaltags": [{"name": "lt-a", "id": "1", "isValid": True}]}
    rows = parse_legal_tags_json(body, data_partition_id="opendes", source="adme_api")
    assert len(rows) == 1
    assert rows[0]["legal_tag_name"] == "lt-a"
    assert rows[0]["data_partition_id"] == "opendes"


def test_parse_groups_list():
    body = [{"id": "g1", "name": "Readers", "description": "x"}]
    rows = parse_entitlements_groups_json(body, data_partition_id="p", source="adme_api")
    assert len(rows) == 1
    assert rows[0]["group_id"] == "g1"

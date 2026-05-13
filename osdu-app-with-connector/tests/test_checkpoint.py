from connector.storage.checkpoint import MemoryCheckpointStore


def test_memory_checkpoint_roundtrip():
    s = MemoryCheckpointStore()
    assert s.get_watermark("wellbore") is None
    s.commit("wellbore", watermark="w1", load_type="incremental", rows_ingested=10)
    assert s.get_watermark("wellbore") == "w1"
    row = s.last("wellbore")
    assert row is not None
    assert row.rows_ingested == 10

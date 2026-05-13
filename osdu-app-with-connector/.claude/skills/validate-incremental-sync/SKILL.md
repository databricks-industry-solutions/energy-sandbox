---
name: validate-incremental-sync
description: Validate that ADME domain tables (wellbore, reservoir, rock_and_fluid) correctly implement CDC incremental sync — offset tracking, watermark filtering, and pagination termination.
---

# Validate Incremental Sync

## Goal

Confirm that:
1. First `read_table(table, None, {})` returns records and an offset
2. Second `read_table(table, offset, {})` with the returned offset returns no new records (stable = done)
3. Incremental filter (`modifyTime:[{watermark} TO *]`) is correctly sent on watermarked reads

## Scope

Only domain tables are CDC: `wellbore`, `reservoir`, `rock_and_fluid`.
Governance tables (`legal_tags`, `entitlements`) are snapshot — always return `offset=None`.

---

## Step 1 — Understand the offset structure

From `connector/lakeflow/adme_osdu.py`:

```python
# After first page
new_offset = {"cursor": next_cursor, "watermark": max_wm}
# next_cursor: None if no next page from ADME cursor field
# max_wm: max modifyTime across returned records
```

On the second call with this offset:
- `cursor = None` (no next page)
- `watermark = "2024-03-17T12:15:00.000Z"` (max from first batch)
- `load_full = False` (watermark is set)
- Body gets `query = "modifyTime:[2024-03-17T12:15:00.000Z TO *]"` via `incremental_filter_template`
- ADME returns nothing newer → empty results → `end_offset == start_offset` → done

---

## Step 2 — Simulate mode validation (no credentials)

```bash
PYTHONPATH=. /Users/gokul.pillai/.ai-dev-kit/.venv/bin/pytest \
  tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py::TestAdmeOsduConnector::test_read_wellbore_twice_returns_same_stable_offset \
  tests/unit/adme_osdu/test_adme_osdu_lakeflow_connect.py::TestAdmeOsduConnector::test_read_terminates \
  -v
```

Both must pass.

---

## Step 3 — Live mode validation (needs token)

```python
import json, sys
sys.path.insert(0, '.')
sys.path.insert(0, 'tests/stubs')

with open('tests/unit/adme_osdu/dev_config.json') as f:
    opts = json.load(f)

from connector.lakeflow.adme_osdu import AdmeOsduLakeflowConnect
c = AdmeOsduLakeflowConnect(opts)

for table in ('wellbore', 'reservoir', 'rock_and_fluid'):
    # Full load
    recs1, off1 = c.read_table(table, None, {})
    all_recs = list(recs1)
    print(f"{table}: {len(all_recs)} records, offset={off1}")
    
    if not all_recs:
        print(f"  ⚠️  No records in {table} — skipping incremental check")
        continue
    
    # Incremental from watermark
    recs2, off2 = c.read_table(table, off1, {})
    new_recs = list(recs2)
    
    if off2 == off1:
        print(f"  ✅ {table}: offset stable (no new records, as expected for same watermark)")
    else:
        print(f"  ℹ️  {table}: new offset {off2} — {len(new_recs)} additional records found")
    
    # Verify cursor field present
    for r in all_recs[:3]:
        assert 'modifyTime' in r, f"{table}: missing modifyTime in record"
    print(f"  ✅ modifyTime present in all sampled records")
```

---

## Step 4 — Validate filtering logic

Midpoint watermark test (live only):

```python
import re
all_modify_times = sorted(r['modifyTime'] for r in all_recs if r.get('modifyTime'))
if len(all_modify_times) >= 2:
    midpoint = all_modify_times[len(all_modify_times) // 2]
    recs_mid, _ = c.read_table(table, {"cursor": None, "watermark": midpoint}, {})
    mid_recs = list(recs_mid)
    violations = [r for r in mid_recs if r.get('modifyTime', '') < midpoint]
    if not violations:
        print(f"  ✅ Midpoint filter correct — no records before {midpoint}")
    else:
        print(f"  ❌ {len(violations)} records before midpoint — incremental filter may be wrong")
```

---

## Pass Criteria

| Check | Expected |
|-------|----------|
| First read returns > 0 records | ✅ |
| Returned offset has `cursor` and `watermark` keys | ✅ |
| `modifyTime` present in all domain records | ✅ |
| Second read with same offset returns stable offset | ✅ |
| `test_read_terminates` completes in < 20 iterations | ✅ |
| No records before midpoint watermark (live) | ✅ |

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Second read returns same records again | `incremental_filter_template` missing | Add it to `_default_domain_config` |
| `test_read_terminates` loops infinitely | Mock not returning empty on incremental query | Check `body.get("query")` in `_search_handler` |
| `modifyTime` missing | Wrong path in `_flatten_record` | Check `r.get("modifyTime")` — top-level field |
| Offset keys differ between reads | Inconsistent offset dict construction | Use same keys in `_read_domain` |

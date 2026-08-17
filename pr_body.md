## Summary

When `active_personality.json` contains `{"personality_id": null}`, `data.get("personality_id", "")` returns `None` (not the default `""`), because `.get()` only uses the default when the key is **absent**, not when the value is `null`. Calling `None.strip()` raises `AttributeError`, crashing the personality resolution chain silently.

## Root Cause

`active.py:143` — `data.get("personality_id", "").strip()` does not handle `null` JSON values.

## Fix

```python
# Before
pid = data.get("personality_id", "").strip()
# After
pid = (data.get("personality_id") or "").strip()
```

## Severity

**HIGH** — Crashes personality loading. The except on line 147 only catches `json.JSONDecodeError` and `IOError`, so `AttributeError` propagates uncaught.

## Reproduction

1. Write `{"personality_id": null}` to `~/.spark/active_personality.json`
2. Call `get_active_personality_id()`
3. `AttributeError: 'NoneType' object has no attribute 'strip'`

## CWE

CWE-476: NULL Pointer Dereference

<details>

```json
{"packet_version":"spark-compete-hotfix-v1","team_details":{"team_name":"Bug Hunters","team_lead_telegram":"@drophub_sir","members":[{"name":"Sampson","telegram":"@drophub_sir","github":"esc1200"},{"name":"ZakJan","telegram":"@Daraking2612","github":"ZakJan777"},{"name":"Saleem","telegram":"@Saleemkhan114","github":"dara917"}]},"issue":{"type":"bug","severity":"HIGH","cwe":"CWE-476","title":"Null personality_id in JSON causes AttributeError crash","affected_file":"src/personality_engine/active.py","affected_line_or_symbol":"143","owner_surface":"personality-chip-labs","evidence_types":["reproduction_steps","test_patch"],"reproduction_steps":"1. Write {\"personality_id\": null} to active_personality.json 2. Call get_active_personality_id() 3. AttributeError","smoke_test":"python -c \"data={'personality_id':None}; pid=(data.get('personality_id') or '').strip(); print(f'OK: {repr(pid)}')\""},"pr":{"url":"PLACEHOLDER","body_must_include":"CWE-476"}}
```

</details>

## Summary

The drift score formula adds `len(signals) * 0.05` without any cap. Twenty barely-detectable signals (severity 0.1 each) produce: `0.1 + 20*0.05 = 1.1`, clamped to 1.0 — maximum drift from harmless signals, triggering unnecessary interventions.

## Fix

Cap the signal count contribution at 0.5:

```python
# Before
sum(s["severity"] for s in signals) / len(signals) + len(signals) * 0.05,
# After
sum(s["severity"] for s in signals) / len(signals) + min(len(signals) * 0.05, 0.5),
```

## CWE

CWE-682: Incorrect Calculation

<details>

```json
{"packet_version":"spark-compete-hotfix-v1","team_details":{"team_name":"Bug Hunters","team_lead_telegram":"@drophub_sir","members":[{"name":"Sampson","telegram":"@drophub_sir","github":"esc1200"},{"name":"ZakJan","telegram":"@Daraking2612","github":"ZakJan777"},{"name":"Saleem","telegram":"@Saleemkhan114","github":"dara917"}]},"issue":{"type":"bug","severity":"MEDIUM","cwe":"CWE-682","title":"Drift score overweights signal count causing false max drift","affected_file":"src/personality_engine/observer.py","affected_line_or_symbol":"57","owner_surface":"personality-chip-labs","evidence_types":["reproduction_steps","test_patch"],"reproduction_steps":"20 signals with severity 0.1: avg=0.1 + 20*0.05=1.1, clamped to 1.0 (max drift from harmless signals)","smoke_test":"python -c \"signals=[{'severity':0.1}]*20; score=min(sum(s['severity'] for s in signals)/len(signals)+min(len(signals)*0.05,0.5),1.0); print(f'Score: {score}')\""},"pr":{"url":"PLACEHOLDER","body_must_include":"CWE-682"}}
```

</details>

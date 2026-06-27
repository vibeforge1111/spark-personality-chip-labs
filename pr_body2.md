## Summary

Dominance baseline weights sum to 0.5+0.3=0.8, while pleasure (0.6+0.4=1.0) and arousal (0.6+0.4=1.0) both sum to 1.0. This causes dominance to be systematically underweighted — its maximum magnitude is only 80% of the other dimensions.

## Fix

Add openness term (0.2) to bring the sum to 1.0:

```python
# Before
d = (chip.conscientiousness - 0.5) * 0.5 + (chip.extraversion - 0.5) * 0.3
# After
d = (chip.conscientiousness - 0.5) * 0.5 + (chip.extraversion - 0.5) * 0.3 + (chip.openness - 0.5) * 0.2
```

## CWE

CWE-682: Incorrect Calculation

<details>

```json
{"packet_version":"spark-compete-hotfix-v1","team_details":{"team_name":"Bug Hunters","team_lead_telegram":"@drophub_sir","members":[{"name":"Sampson","telegram":"@drophub_sir","github":"esc1200"},{"name":"ZakJan","telegram":"@Daraking2612","github":"ZakJan777"},{"name":"Saleem","telegram":"@Saleemkhan114","github":"dara917"}]},"issue":{"type":"bug","severity":"MEDIUM","cwe":"CWE-682","title":"Dominance weight sum is 0.8 instead of 1.0","affected_file":"src/personality_engine/emotional_state.py","affected_line_or_symbol":"162","owner_surface":"personality-chip-labs","evidence_types":["reproduction_steps","test_patch"],"reproduction_steps":"Compare pleasure weights (0.6+0.4=1.0), arousal weights (0.6+0.4=1.0) vs dominance weights (0.5+0.3=0.8)","smoke_test":"assert 0.5+0.3+0.2 == 1.0"},"pr":{"url":"PLACEHOLDER","body_must_include":"CWE-682"}}
```

</details>

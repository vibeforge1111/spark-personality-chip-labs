# Spark Personality Chip Labs

Public personality chip lab for Spark agents.

This repo defines portable personality chips that can be loaded by Spark Builder,
`spark-character`, or another host runtime without hard-coding voice, emotional
style, or behavior rules into the core agent.

## What This Provides

- YAML personality chip schema
- personality loader and registry helpers
- active personality resolution
- room-reading and emotional-state helpers
- Spark hook entrypoint
- example personalities
- tests for schema, hooks, active personality, and Builder integration boundaries

## Public Boundary

This repo is safe to use as a public local experiment repo. It does not require
API keys for tests or local schema validation.

Keep these boundaries clear:

- public: personality schemas, example personality chips, loader code, tests,
  docs, and local validation scripts
- private/user-owned: local `.personality` selections, generated personality
  evolution notes, private user preferences, runtime memory, transcripts, and
  any host Spark state under `~/.spark`
- not included: live Spark runtime credentials, provider keys, Telegram tokens,
  private Spark Swarm runtime state, or legacy `spark-voice-engine` assets

Do not commit `.env` files, provider credentials, private transcripts, or
runtime state snapshots.

The current public relationship is:

- `spark-personality-chip-labs` owns portable personality chip schemas and experiments.
- `spark-character` owns Spark's default persona, provider overlays, scoring, and evolution gates.
- `spark-voice-comms` owns speech I/O hooks and uses Spark character/personality context when a host runtime connects them.

## Install

```bash
git clone https://github.com/vibeforge1111/spark-personality-chip-labs.git
cd spark-personality-chip-labs
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Use

Validate a personality file:

```bash
python scripts/validate_personality.py personalities/forge.personality.yaml
```

Run the Spark hook:

```bash
python -m personality_engine.spark_hook personality --payload-json "{\"action\":\"status\"}"
```

Set a local active personality from a host Spark environment:

```python
from personality_engine.active import set_active_personality

set_active_personality("forge")
```

Local active selection writes to `~/.spark/active_personality.json`. That file
is user-owned runtime state and should not be committed.

## Relationship To Spark Character

`spark-character` keeps Spark's core persona, voice consistency, scoring, and
provider overlays stable.

`spark-personality-chip-labs` is the experimental chip layer for alternate
personalities, archetypes, room-reading behavior, and modular personality
profiles.

Use Spark Character for the default Spark voice. Use this repo when you want a
portable personality chip that can be selected, validated, and tested.

## Security

Read [SECURITY.md](./SECURITY.md) before publishing a fork or adding generated
personality artifacts.

## License

AGPL-3.0-only. See [LICENSE](./LICENSE).


<!-- Security patch 951 applied: [hash:jgy1s16v61] -->
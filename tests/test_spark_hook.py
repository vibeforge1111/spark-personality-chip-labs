from __future__ import annotations

import json
from unittest.mock import patch

from personality_engine.schema import PersonalityChip
from personality_engine.spark_hook import handle_personality_hook, main


def _make_chip(**overrides) -> PersonalityChip:
    defaults = {
        "id": "forge",
        "name": "Forge",
        "archetype": "builder",
        "voice_signature": "direct, energetic, action-biased",
        "tagline": "Ship it, learn, ship again.",
        "openness": 0.60,
        "conscientiousness": 0.80,
        "extraversion": 0.75,
        "agreeableness": 0.50,
        "neuroticism": 0.20,
        "social_awareness": 0.55,
        "empathy_style": "directive",
        "communication": {
            "verbosity": "terse",
            "formality": "casual",
            "explanation_style": "stepwise",
            "humor_frequency": "occasional",
        },
        "decision_making": {"risk_appetite": "bold"},
    }
    defaults.update(overrides)
    return PersonalityChip(**defaults)


class TestHandlePersonalityHook:
    def test_returns_builder_contract_for_active_chip(self, tmp_path):
        evolver_path = tmp_path / "personality_evolution_v1.json"
        with patch("personality_engine.spark_hook.get_active_personality", return_value=_make_chip()):
            payload = handle_personality_hook(
                {
                    "human_id": "human:telegram:111",
                    "agent_id": "agent:human:telegram:111",
                    "evolver_state_path": str(evolver_path),
                }
            )

        assert payload["returncode"] == 0
        assert payload["result"]["persona_name"] == "Forge"
        assert payload["result"]["personality_id"] == "forge"
        assert payload["result"]["base_traits"] == payload["result"]["evolver_state"]["traits"]
        assert evolver_path.exists()


class TestSparkHookMain:
    def test_main_writes_error_when_input_file_is_missing(self, tmp_path, monkeypatch):
        input_path = tmp_path / "missing.json"
        output_path = tmp_path / "output.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "personality_engine.spark_hook",
                "personality",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
        )

        exit_code = main()

        assert exit_code == 1
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["returncode"] == 1
        assert payload["error"] == "Spark hook input file not found."
        assert str(input_path) not in json.dumps(payload)
        assert payload["result"] == {}

    def test_main_writes_error_when_input_payload_is_not_object(self, tmp_path, monkeypatch):
        input_path = tmp_path / "input.json"
        output_path = tmp_path / "output.json"
        input_path.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(
            "sys.argv",
            [
                "personality_engine.spark_hook",
                "personality",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
        )

        exit_code = main()

        assert exit_code == 1
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["error"] == "Spark hook input payload must be a JSON object."

    def test_main_rejects_oversized_input_before_hook_execution(self, tmp_path, monkeypatch):
        input_path = tmp_path / "input.json"
        output_path = tmp_path / "output.json"
        input_path.write_text('{"note":"' + ("x" * 1_000_001) + '"}', encoding="utf-8")
        monkeypatch.setattr(
            "sys.argv",
            [
                "personality_engine.spark_hook",
                "personality",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
        )

        exit_code = main()

        assert exit_code == 1
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["error"] == "Spark hook input payload is too large."

    def test_main_writes_error_when_no_active_personality(self, tmp_path, monkeypatch):
        input_path = tmp_path / "input.json"
        output_path = tmp_path / "output.json"
        input_path.write_text(
            json.dumps(
                {
                    "human_id": "human:telegram:111",
                    "agent_id": "agent:human:telegram:111",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "sys.argv",
            [
                "personality_engine.spark_hook",
                "personality",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
        )
        with patch("personality_engine.spark_hook.get_active_personality", return_value=None):
            exit_code = main()

        assert exit_code == 1
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["error"].startswith("No active personality chip is configured.")

"""Tests for personality chip loader."""

import pytest
import tempfile
from pathlib import Path

from personality_engine.loader import load_personality, load_all_personalities

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@pytest.fixture
def tmp_personality_dir(tmp_path):
    """Create a temp directory with a valid personality chip."""
    chip_file = tmp_path / "test-agent.personality.yaml"
    chip_file.write_text(
        "schema: spark-personality-chip.v1\n"
        "identity:\n"
        "  id: test-agent\n"
        "  name: Test Agent\n"
        "  archetype: builder\n"
        "traits:\n"
        "  openness: 0.75\n"
        "  conscientiousness: 0.60\n"
    )
    return tmp_path


@pytest.fixture
def tmp_multifile_dir(tmp_path):
    """Create a temp directory with a multifile personality chip."""
    chip_dir = tmp_path / "multi-agent"
    chip_dir.mkdir()

    (chip_dir / "personality.yaml").write_text(
        "schema: spark-personality-chip.v1\n"
        "identity:\n"
        "  id: multi-agent\n"
        "  name: Multi Agent\n"
        "traits:\n"
        "  openness: 0.50\n"
    )

    (chip_dir / "traits.yaml").write_text(
        "openness: 0.90\n"
        "conscientiousness: 0.80\n"
    )

    (chip_dir / "preferences.yaml").write_text(
        "preferences:\n"
        "  communication:\n"
        "    verbosity: terse\n"
    )

    return tmp_path


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
class TestLoadSingleFile:

    def test_load_valid_chip(self, tmp_personality_dir):
        chip_path = tmp_personality_dir / "test-agent.personality.yaml"
        chip = load_personality(chip_path)
        assert chip.id == "test-agent"
        assert chip.name == "Test Agent"
        assert chip.openness == 0.75

    def test_load_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_personality("/nonexistent/path.personality.yaml")

    def test_load_invalid_spec(self, tmp_path):
        bad = tmp_path / "bad.personality.yaml"
        bad.write_text("identity:\n  name: NoId\n")
        with pytest.raises(ValueError, match="validation failed"):
            load_personality(bad)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
class TestLoadMultifile:

    def test_load_directory_format(self, tmp_multifile_dir):
        chip_dir = tmp_multifile_dir / "multi-agent"
        chip = load_personality(chip_dir)
        assert chip.id == "multi-agent"
        # traits.yaml overlay should override openness
        assert chip.openness == 0.90
        assert chip.conscientiousness == 0.80

    def test_malformed_optional_overlay_is_skipped(self, tmp_multifile_dir):
        chip_dir = tmp_multifile_dir / "multi-agent"
        (chip_dir / "traits.yaml").write_text("traits:\n  openness: [\n", encoding="utf-8")

        chip = load_personality(chip_dir)

        assert chip.id == "multi-agent"
        assert chip.openness == 0.50

    def test_directory_missing_personality_yaml(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            load_personality(empty_dir)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
class TestLoadAll:

    def test_load_all_from_directory(self, tmp_personality_dir):
        chips = load_all_personalities(tmp_personality_dir)
        assert len(chips) == 1
        assert chips[0].id == "test-agent"

    def test_load_all_empty_dir(self, tmp_path):
        chips = load_all_personalities(tmp_path)
        assert chips == []

    def test_load_all_skips_invalid(self, tmp_path):
        # Valid chip
        valid = tmp_path / "good.personality.yaml"
        valid.write_text(
            "identity:\n  id: good-bot\n  name: Good\n"
        )
        # Invalid chip (no id)
        invalid = tmp_path / "bad.personality.yaml"
        invalid.write_text(
            "identity:\n  name: NoId\n"
        )
        chips = load_all_personalities(tmp_path)
        assert len(chips) == 1
        assert chips[0].id == "good-bot"


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
class TestRepoPersonalities:

    def test_founder_operator_personality_loads(self):
        repo_root = Path(__file__).resolve().parents[1]
        chip = load_personality(repo_root / "personalities" / "founder-operator.personality.yaml")
        assert chip.id == "founder-operator"
        assert chip.name == "Founder Operator"
        assert chip.voice_signature == "direct, calm, low-fluff, strategic"

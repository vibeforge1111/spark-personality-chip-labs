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


def test_corrupt_overlay_produces_warning_not_silent_skip(tmp_path):
    """Corrupted overlay YAML must produce _overlay_load_warnings, not silent skip."""
    if not HAS_YAML:
        pytest.skip("PyYAML not installed")

    # Valid base personality
    base = tmp_path / "personality.yaml"
    base.write_text(
        "schema: spark-personality-chip.v1\n"
        "identity:\n"
        "  id: corrupt-overlay-test\n"
        "  name: Corrupt Overlay Test\n"
        "  archetype: builder\n"
        "traits:\n"
        "  openness: 0.7\n"
    )

    # Corrupt safety.yaml — missing colon
    (tmp_path / "safety.yaml").write_text("harm_avoidance\n  - test: broken\n")

    chip = load_personality(tmp_path)

    warnings = chip._raw.get("_overlay_load_warnings", [])
    assert len(warnings) >= 1, f"Expected warning for corrupt overlay, got {warnings}"
    assert any("safety.yaml" in w for w in warnings), f"Warning must name safety.yaml: {warnings}"


def test_corrupt_custom_overlay_preserves_core_without_reflecting_details(tmp_path):
    if not HAS_YAML:
        pytest.skip("PyYAML not installed")
    (tmp_path / "personality.yaml").write_text(
        "identity:\n  id: safe-core\n  name: Safe Core\n", encoding="utf-8"
    )
    (tmp_path / "custom.yaml").write_text("secret-path:\n  - [unclosed\n", encoding="utf-8")
    chip = load_personality(tmp_path)
    assert chip.id == "safe-core"
    assert chip._raw["_overlay_load_warnings"] == ["custom.yaml: ParserError"]
    assert "secret-path" not in chip._raw["_overlay_load_warnings"][0]


def test_load_all_skips_symlinked_personality(tmp_path):
    if not HAS_YAML:
        pytest.skip("PyYAML not installed")
    outside = tmp_path / "outside.personality.yaml"
    outside.write_text("identity:\n  id: outside-chip\n  name: Outside\n", encoding="utf-8")
    directory = tmp_path / "chips"
    directory.mkdir()
    (directory / "linked.personality.yaml").symlink_to(outside)
    assert load_all_personalities(directory) == []


def test_yaml_loader_accepts_utf8_bom(tmp_path):
    path = tmp_path / "bom.personality.yaml"
    path.write_bytes(b"\xef\xbb\xbfidentity:\n  id: bom-chip\n  name: BOM Chip\n")
    assert load_personality(path).id == "bom-chip"


def test_deep_merge_is_bounded_and_preserves_shallow_nested_values():
    from personality_engine.loader import _MAX_MERGE_DEPTH, _deep_merge
    base = {"a": {"keep": 1}}
    _deep_merge(base, {"a": {"add": 2}})
    assert base == {"a": {"keep": 1, "add": 2}}
    deep_base, deep_overlay = {}, {}
    right = deep_overlay
    for index in range(_MAX_MERGE_DEPTH + 1):
        right[str(index)] = {}
        right = right[str(index)]
    with pytest.raises(RecursionError, match="exceeds"):
        _deep_merge(deep_base, deep_overlay)
    assert deep_base == {}


def test_overdeep_overlay_is_rejected_atomically(tmp_path):
    if not HAS_YAML:
        pytest.skip("PyYAML not installed")
    from personality_engine.loader import _MAX_MERGE_DEPTH

    (tmp_path / "personality.yaml").write_text(
        "identity:\n  id: depth-owner\n  name: Depth Owner\ntraits:\n  openness: 0.7\n",
        encoding="utf-8",
    )
    deep = {}
    cursor = deep
    for index in range(_MAX_MERGE_DEPTH + 1):
        cursor[str(index)] = {}
        cursor = cursor[str(index)]
    (tmp_path / "traits.yaml").write_text(yaml.safe_dump(deep), encoding="utf-8")

    chip = load_personality(tmp_path)
    assert chip.openness == 0.7
    assert chip._raw["traits"] == {"openness": 0.7}
    assert chip._raw["_overlay_load_warnings"] == ["traits.yaml: RecursionError"]


def test_list_overlay_replaces_base_instead_of_duplicating_it(tmp_path):
    if not HAS_YAML:
        pytest.skip("PyYAML not installed")
    (tmp_path / "personality.yaml").write_text(
        "identity:\n  id: list-owner\n  name: List Owner\nstrengths:\n  - trait: old\n",
        encoding="utf-8",
    )
    (tmp_path / "strengths.yaml").write_text("strengths:\n  - trait: new\n", encoding="utf-8")
    assert [item["trait"] for item in load_personality(tmp_path).strengths] == ["new"]


def test_malformed_mapping_overlay_preserves_core_section(tmp_path):
    if not HAS_YAML:
        pytest.skip("PyYAML not installed")
    (tmp_path / "personality.yaml").write_text(
        "identity:\n  id: shape-owner\n  name: Shape Owner\ntraits:\n  openness: 0.7\n",
        encoding="utf-8",
    )
    (tmp_path / "traits.yaml").write_text("traits:\n  - malformed\n", encoding="utf-8")
    chip = load_personality(tmp_path)
    assert chip.openness == 0.7
    assert chip._raw["traits"] == {"openness": 0.7}
    assert chip._raw["_overlay_load_warnings"] == ["traits.yaml: TypeError"]

"""
Personality Drift Observer

Monitors agent responses for personality consistency.
Detects when an agent's output drifts from its personality chip.

Logs drift signals to ~/.spark/chip_insights/personality_{id}.jsonl
following the same JSONL format as Spark Intelligence Builder.

Lightweight: Keyword-based detection, no ML inference required.
"""

import fcntl
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# fcntl is POSIX-only; guard the import so the observer module still loads on
# Windows. When it is unavailable we simply skip advisory file locking.
try:
    import fcntl
except ImportError:  # pragma: no cover - Windows / non-POSIX
    fcntl = None

from .schema import PersonalityChip

# Validate personality_id for safe use in log file paths. Kept permissive
# (letters, digits, '_' and '-', any case, length 1-64) so legitimate ids are
# accepted, while '/', '\\', '.', whitespace and '..' are still rejected.
_VALID_LOG_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _safe_log_id(personality_id: str) -> str:
    """Return a safe version of personality_id for use in file paths.

    Rejects values containing path separators or outside the expected format.
    Returns empty string if the ID is unsafe.
    """
    if not personality_id or not isinstance(personality_id, str):
        return ""
    pid = personality_id.strip()
    if _VALID_LOG_ID_RE.match(pid):
        return pid
    return ""

INSIGHTS_DIR = Path.home() / ".spark" / "chip_insights"


def observe_response(
    chip: PersonalityChip,
    response_text: str,
    user_message: str = "",
    session_id: str = "default",
) -> dict:
    """
    Check an agent response against its personality chip.

    Returns a drift report:
    {
        "personality_id": str,
        "drift_score": float (0.0 = perfect match, 1.0 = full drift),
        "signals": [{"type": str, "detail": str, "severity": float}],
        "recommendation": str | None,
    }
    """
    signals = []

    # Check anti-pattern violations
    ap_signals = _check_anti_patterns(chip, response_text)
    signals.extend(ap_signals)

    # Check voice consistency
    voice_signals = _check_voice_consistency(chip, response_text)
    signals.extend(voice_signals)

    # Check emotional range violations
    emotion_signals = _check_emotional_range(chip, response_text)
    signals.extend(emotion_signals)

    # Calculate composite drift score
    if signals:
        drift_score = min(
            sum(s["severity"] for s in signals) / len(signals) + len(signals) * 0.05,
            1.0
        )
    else:
        drift_score = 0.0

    recommendation = None
    if drift_score >= 0.6:
        recommendation = "High drift detected - consider re-grounding agent with personality context."
    elif drift_score >= 0.3:
        recommendation = "Moderate drift - review adaptive behavior triggers."

    report = {
        "personality_id": chip.id,
        "drift_score": round(drift_score, 3),
        "signals": signals,
        "recommendation": recommendation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
    }

    # Log if any drift detected
    if signals:
        _log_drift(chip.id, report)

    return report


def get_drift_history(
    personality_id: str,
    limit: int = 50,
) -> list[dict]:
    """Read recent drift signals from the insights log."""
    safe_id = _safe_log_id(personality_id)
    if not safe_id:
        return []
    log_path = INSIGHTS_DIR / f"personality_{safe_id}.jsonl"
    if not log_path.exists():
        return []

    entries = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except IOError:
        return []

    return entries[-limit:]


# ── Detection Functions ──

def _check_anti_patterns(chip: PersonalityChip, text: str) -> list[dict]:
    """Check if response violates any anti-patterns."""
    signals = []
    text_lower = text.lower()

    # Map anti-pattern descriptions to detectable patterns
    violation_patterns = {
        "dismiss": ["that's not important", "doesn't matter", "who cares", "irrelevant"],
        "jargon": [],  # Hard to detect without context — skip keyword matching
        "timeline": ["this will take", "should be done by", "estimate", "eta", "within hours"],
        "pretend": ["i'm certain", "i guarantee", "definitely works", "trust me on this"],
        "sycophant": ["you're absolutely right", "brilliant idea", "couldn't agree more",
                      "perfect approach"],
        "manipulat": ["you should really", "you need to", "you must", "don't you think"],
        "urgency": ["act now", "hurry", "immediately", "don't wait", "urgent"],
    }

    for ap in chip.anti_patterns:
        ap_lower = ap.lower()
        matched = False
        for keyword, detectors in violation_patterns.items():
            if matched:
                break
            if keyword in ap_lower:
                for detector in detectors:
                    if detector in text_lower:
                        signals.append({
                            "type": "anti_pattern_violation",
                            "detail": f"Violated: '{ap}' - detected '{detector}'",
                            "severity": 0.7,
                        })
                        matched = True
                        break  # One violation per anti-pattern is enough

    return signals


def _check_voice_consistency(chip: PersonalityChip, text: str) -> list[dict]:
    """Check if response matches the personality's communication style."""
    signals = []

    comm = chip.communication
    if not comm:
        return signals

    verbosity = comm.get("verbosity", "moderate")
    formality = comm.get("formality", "professional")

    word_count = len(text.split())

    # Verbosity check
    if verbosity == "terse" and word_count > 300:
        signals.append({
            "type": "voice_drift",
            "detail": f"Personality is terse but response has {word_count} words",
            "severity": 0.3,
        })
    elif verbosity == "detailed" and word_count < 30:
        signals.append({
            "type": "voice_drift",
            "detail": f"Personality is detailed but response has only {word_count} words",
            "severity": 0.2,
        })

    # Formality check
    casual_markers = ["lol", "gonna", "wanna", "kinda", "tbh", "ngl", "fr fr"]
    academic_markers = ["furthermore", "consequently", "notwithstanding", "heretofore"]

    text_lower = text.lower()
    if formality == "professional":
        casual_count = sum(1 for m in casual_markers if m in text_lower)
        if casual_count >= 2:
            signals.append({
                "type": "voice_drift",
                "detail": f"Professional tone but found {casual_count} casual markers",
                "severity": 0.4,
            })
    elif formality == "casual":
        academic_count = sum(1 for m in academic_markers if m in text_lower)
        if academic_count >= 2:
            signals.append({
                "type": "voice_drift",
                "detail": f"Casual tone but found {academic_count} academic markers",
                "severity": 0.3,
            })

    return signals


def _check_emotional_range(chip: PersonalityChip, text: str) -> list[dict]:
    """Check if response shows emotions outside the personality's range."""
    signals = []
    text_lower = text.lower()

    # Emotion detection keywords
    emotion_markers = {
        "frustration": ["frustrated", "annoying", "ugh", "this is ridiculous"],
        "excitement": ["amazing", "incredible", "wow", "awesome", "fantastic", "!!!"],
        "humor": ["haha", "lol", "joke", "funny", "😄", "😂"],
    }

    for emotion, markers in emotion_markers.items():
        intensity_in_text = sum(1 for m in markers if m in text_lower)
        if intensity_in_text == 0:
            continue

        configured_range = chip.emotional_range.get(emotion, 0.50)

        # If personality has low range for this emotion but text shows high expression
        if configured_range <= 0.25 and intensity_in_text >= 2:
            signals.append({
                "type": "emotional_range_violation",
                "detail": (
                    f"Personality has low {emotion} ({configured_range}) "
                    f"but response shows {intensity_in_text} markers"
                ),
                "severity": 0.4,
            })

    return signals


# ── Logging ──

_MAX_LOG_LINES = 500  # Rotate after this many entries


def _log_drift(personality_id: str, report: dict) -> None:
    """Append drift report to JSONL insights log."""
    safe_id = _safe_log_id(personality_id)
    if not safe_id:
        return
    INSIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = INSIGHTS_DIR / f"personality_{safe_id}.jsonl"

    entry = {
        "chip_id": f"personality_{safe_id}",
        "content": f"Drift detected (score: {report['drift_score']})",
        "confidence": 1.0 - report["drift_score"],
        "timestamp": report["timestamp"],
        "observer_name": "personality_drift",
        "captured_data": {
            "drift_score": report["drift_score"],
            "signal_count": len(report["signals"]),
            "signals": report["signals"][:5],  # Cap stored signals
            "session_id": report["session_id"],
        },
    }

    try:
        _rotate_log_if_needed(log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            if fcntl is not None:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.write(json.dumps(entry) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            else:
                f.write(json.dumps(entry) + "\n")
    except IOError:
        pass


def _rotate_log_if_needed(log_path: Path) -> None:
    """Trim JSONL log to the most recent _MAX_LOG_LINES entries."""
    if not log_path.exists():
        return
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= _MAX_LOG_LINES:
            return
        # Keep only the last _MAX_LOG_LINES entries
        with open(log_path, "w", encoding="utf-8") as f:
            f.writelines(lines[-_MAX_LOG_LINES:])
    except IOError:
        pass

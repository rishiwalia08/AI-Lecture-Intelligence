"""
tests/test_pii_cleaner.py
--------------------------
Unit tests for src.anonymization.pii_cleaner
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.anonymization.pii_cleaner import PIICleaner


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def cleaner() -> PIICleaner:
    """Shared PIICleaner instance (avoids reloading spaCy per test)."""
    return PIICleaner()


# ──────────────────────────────────────────────────────────────
# clean_text_pii tests
# ──────────────────────────────────────────────────────────────
class TestCleanTextPII:
    def test_person_replaced(self, cleaner: PIICleaner) -> None:
        text = "Yesterday Rahul asked a question in the class."
        cleaned = cleaner.clean_text_pii(text)
        assert "[PERSON]" in cleaned
        assert "Rahul" not in cleaned

    def test_empty_string_unchanged(self, cleaner: PIICleaner) -> None:
        assert cleaner.clean_text_pii("") == ""

    def test_no_pii_unchanged(self, cleaner: PIICleaner) -> None:
        text = "Water boils at 100 degrees Celsius."
        cleaned = cleaner.clean_text_pii(text)
        assert cleaned == text

    def test_multiple_persons_replaced(self, cleaner: PIICleaner) -> None:
        text = "Alice and Bob collaborated on the project."
        cleaned = cleaner.clean_text_pii(text)
        assert "Alice" not in cleaned
        assert "Bob" not in cleaned

    def test_output_length_reasonable(self, cleaner: PIICleaner) -> None:
        """Output should not be empty for non-trivial input."""
        text = "Google was founded by Larry Page."
        cleaned = cleaner.clean_text_pii(text)
        assert len(cleaned) > 5


# ──────────────────────────────────────────────────────────────
# get_pii_entities tests
# ──────────────────────────────────────────────────────────────
class TestGetPIIEntities:
    def test_returns_list(self, cleaner: PIICleaner) -> None:
        entities = cleaner.get_pii_entities("Hello world.")
        assert isinstance(entities, list)

    def test_entity_has_expected_keys(self, cleaner: PIICleaner) -> None:
        text = "Barack Obama was born in Hawaii."
        entities = cleaner.get_pii_entities(text)
        if entities:
            entity = entities[0]
            assert "text" in entity
            assert "label" in entity
            assert "start" in entity
            assert "end" in entity


# ──────────────────────────────────────────────────────────────
# process_transcript_file tests
# ──────────────────────────────────────────────────────────────
class TestProcessTranscriptFile:
    def test_text_file_cleaned(self, tmp_path: Path, cleaner: PIICleaner) -> None:
        src = tmp_path / "transcript.txt"
        dst = tmp_path / "transcript_clean.txt"
        src.write_text("Tesla was founded by Elon Musk.", encoding="utf-8")

        ok = cleaner.process_transcript_file(src, dst)

        assert ok is True
        assert dst.exists()
        content = dst.read_text(encoding="utf-8")
        assert "Elon Musk" not in content

    def test_json_file_cleaned(self, tmp_path: Path, cleaner: PIICleaner) -> None:
        src = tmp_path / "transcript.json"
        dst = tmp_path / "transcript_clean.json"
        data = {"text": "Priya joined Microsoft last year."}
        src.write_text(json.dumps(data), encoding="utf-8")

        ok = cleaner.process_transcript_file(src, dst)

        assert ok is True
        cleaned = json.loads(dst.read_text())
        assert "Priya" not in cleaned["text"]

    def test_missing_file_returns_false(self, tmp_path: Path, cleaner: PIICleaner) -> None:
        result = cleaner.process_transcript_file(
            tmp_path / "ghost.txt", tmp_path / "out.txt"
        )
        assert result is False

    def test_creates_output_dir(self, tmp_path: Path, cleaner: PIICleaner) -> None:
        src = tmp_path / "input.txt"
        dst = tmp_path / "deep" / "nested" / "out.txt"
        src.write_text("Hello world.", encoding="utf-8")

        ok = cleaner.process_transcript_file(src, dst)

        assert ok is True
        assert dst.exists()

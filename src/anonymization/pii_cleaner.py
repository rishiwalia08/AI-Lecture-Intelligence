"""
src/anonymization/pii_cleaner.py
---------------------------------
PII anonymization module for the Speech RAG system — Phase 1.

Uses spaCy Named Entity Recognition to detect and replace personally
identifiable information in lecture transcripts.

Supported entity types and their replacements (configurable):
  PERSON → [PERSON]
  ORG    → [ORG]
  GPE    → [LOCATION]

Usage
-----
    from src.anonymization.pii_cleaner import PIICleaner

    cleaner = PIICleaner()

    # Single string
    clean = cleaner.clean_text_pii("Yesterday Rahul asked a question.")
    # → "Yesterday [PERSON] asked a question."

    # File
    cleaner.process_transcript_file("data/transcripts/lecture1.txt",
                                    "data/transcripts/lecture1_clean.txt")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import spacy
import yaml
from tqdm import tqdm

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Default configuration
# ──────────────────────────────────────────────────────────────
DEFAULT_ENTITY_REPLACEMENTS: Dict[str, str] = {
    "PERSON":   "[PERSON]",
    "ORG":      "[ORG]",
    "GPE":      "[LOCATION]",
}

DEFAULT_SPACY_MODEL = "en_core_web_sm"


# ──────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────
class PIICleaner:
    """
    Detect and replace PII in text using spaCy NER.

    Parameters
    ----------
    spacy_model : str
        Name of the spaCy model to load (default ``en_core_web_sm``).
    entity_replacements : dict, optional
        Mapping of NER label → replacement token.  Defaults to
        ``DEFAULT_ENTITY_REPLACEMENTS``.
    config_path : str | Path, optional
        Path to ``config/config.yaml``.  If provided, PII settings
        from the config override the defaults.
    """

    def __init__(
        self,
        spacy_model: str = DEFAULT_SPACY_MODEL,
        entity_replacements: Optional[Dict[str, str]] = None,
        config_path: Optional[str | Path] = None,
    ) -> None:
        if config_path:
            cfg = self._load_config(config_path)
            spacy_model = cfg.get("spacy_model", spacy_model)
            entity_replacements = self._build_replacements_from_config(cfg)

        self.entity_replacements = entity_replacements or DEFAULT_ENTITY_REPLACEMENTS
        self.nlp = self._load_spacy(spacy_model)
        logger.info(
            "PIICleaner ready. Model='%s'  entities=%s",
            spacy_model,
            list(self.entity_replacements.keys()),
        )

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────
    def clean_text_pii(self, text: str) -> str:
        """
        Replace PII entities in *text* with their token counterparts.

        Entities are replaced **right-to-left** in the string to
        preserve character offsets during substitution.

        Parameters
        ----------
        text : str
            Raw transcript text.

        Returns
        -------
        str
            Anonymized text.

        Examples
        --------
        >>> cleaner = PIICleaner()
        >>> cleaner.clean_text_pii("Yesterday Rahul asked a question in the class")
        'Yesterday [PERSON] asked a question in the class'
        """
        if not text or not text.strip():
            return text

        doc = self.nlp(text)
        replacements: List[Tuple[int, int, str]] = []

        for ent in doc.ents:
            if ent.label_ in self.entity_replacements:
                token = self.entity_replacements[ent.label_]
                replacements.append((ent.start_char, ent.end_char, token))
                logger.debug(
                    "PII detected: '%s' (%s) → '%s'", ent.text, ent.label_, token
                )

        # Apply replacements from the end to preserve offsets
        cleaned = list(text)
        for start, end, token in sorted(replacements, reverse=True):
            cleaned[start:end] = list(token)

        return "".join(cleaned)

    def get_pii_entities(self, text: str) -> List[Dict]:
        """
        Return a list of detected PII entities without modifying text.

        Parameters
        ----------
        text : str
            Raw transcript text.

        Returns
        -------
        list of dict
            Each dict contains ``text``, ``label``, ``start``, ``end``.
        """
        doc = self.nlp(text)
        return [
            {
                "text":  ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end":   ent.end_char,
            }
            for ent in doc.ents
            if ent.label_ in self.entity_replacements
        ]

    def process_transcript_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> bool:
        """
        Anonymize a single transcript file and write the result.

        Supports plain text (``.txt``) and JSON files.  For JSON the
        function expects either a top-level ``"text"`` key or a list of
        segment dicts each containing ``"text"``.

        Parameters
        ----------
        input_path : str | Path
            Path to the source transcript.
        output_path : str | Path
            Destination path for the anonymized transcript.

        Returns
        -------
        bool
            True on success, False on failure.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            logger.error("Transcript file not found: '%s'", input_path)
            return False

        try:
            suffix = input_path.suffix.lower()
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if suffix == ".json":
                return self._process_json_file(input_path, output_path)
            else:
                return self._process_text_file(input_path, output_path)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error processing transcript '%s': %s", input_path, exc
            )
            return False

    def batch_process_transcripts(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        extensions: tuple[str, ...] = (".txt", ".json"),
    ) -> Dict[str, int]:
        """
        Anonymize all transcript files in a directory tree.

        Parameters
        ----------
        input_dir : str | Path
            Directory containing raw transcripts.
        output_dir : str | Path
            Mirror directory for anonymized transcripts.
        extensions : tuple
            File extensions to process.

        Returns
        -------
        dict
            ``{"success": int, "failed": int, "skipped": int}``
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)

        files = [
            f for ext in extensions for f in input_dir.rglob(f"*{ext}")
        ]
        logger.info(
            "Batch PII cleaning: %d files from '%s'", len(files), input_dir
        )

        stats = {"success": 0, "failed": 0, "skipped": 0}

        for file_path in tqdm(files, desc="PII Cleaning", unit="file"):
            try:
                rel = file_path.relative_to(input_dir)
            except ValueError:
                rel = Path(file_path.name)

            out_path = output_dir / rel
            ok = self.process_transcript_file(file_path, out_path)
            if ok:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        logger.info("Batch PII cleaning done: %s", stats)
        return stats

    # ──────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _load_spacy(model_name: str) -> spacy.language.Language:
        """Load a spaCy model, with a helpful error on missing model."""
        try:
            nlp = spacy.load(model_name)
            logger.info("spaCy model '%s' loaded.", model_name)
            return nlp
        except OSError as exc:
            logger.error(
                "spaCy model '%s' not found. Run: python -m spacy download %s",
                model_name,
                model_name,
            )
            raise RuntimeError(
                f"spaCy model '{model_name}' not found. "
                f"Install it with: python -m spacy download {model_name}"
            ) from exc

    @staticmethod
    def _load_config(config_path: str | Path) -> dict:
        """Read YAML config."""
        config_path = Path(config_path)
        with config_path.open() as fh:
            return yaml.safe_load(fh)

    @staticmethod
    def _build_replacements_from_config(cfg: dict) -> Dict[str, str]:
        """Extract PII entity→replacement mapping from config dict."""
        entities: list[str] = cfg.get("pii_entities", [])
        replacements_cfg: dict = cfg.get("pii_replacements", {})
        return {
            entity: replacements_cfg.get(entity, f"[{entity}]")
            for entity in entities
        }

    def _process_text_file(
        self, input_path: Path, output_path: Path
    ) -> bool:
        """Read, clean, and write a plain-text transcript."""
        raw = input_path.read_text(encoding="utf-8")
        cleaned = self.clean_text_pii(raw)
        output_path.write_text(cleaned, encoding="utf-8")
        logger.info("Cleaned transcript written to '%s'", output_path)
        return True

    def _process_json_file(
        self, input_path: Path, output_path: Path
    ) -> bool:
        """
        Read, clean and write a JSON transcript.

        Handles two JSON shapes:
          1. ``{"text": "..."}`` — single transcript string.
          2. ``[{"text": "...", ...}, ...]`` — list of segment dicts.
        """
        with input_path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        if isinstance(data, dict) and "text" in data:
            data["text"] = self.clean_text_pii(data["text"])
        elif isinstance(data, list):
            for segment in data:
                if isinstance(segment, dict) and "text" in segment:
                    segment["text"] = self.clean_text_pii(segment["text"])
        else:
            logger.warning(
                "Unexpected JSON structure in '%s'; skipping.", input_path
            )
            return False

        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        logger.info("Cleaned JSON transcript written to '%s'", output_path)
        return True


# ──────────────────────────────────────────────────────────────
# Convenience functions (module-level)
# ──────────────────────────────────────────────────────────────
def clean_text_pii(
    text: str,
    spacy_model: str = DEFAULT_SPACY_MODEL,
) -> str:
    """
    Module-level convenience wrapper around :meth:`PIICleaner.clean_text_pii`.

    Creates a one-shot ``PIICleaner`` instance. For repeated calls prefer
    instantiating ``PIICleaner`` directly to avoid reloading the model.
    """
    cleaner = PIICleaner(spacy_model=spacy_model)
    return cleaner.clean_text_pii(text)


def process_transcript_file(
    input_path: str | Path,
    output_path: str | Path,
    spacy_model: str = DEFAULT_SPACY_MODEL,
) -> bool:
    """Module-level convenience wrapper around :meth:`PIICleaner.process_transcript_file`."""
    cleaner = PIICleaner(spacy_model=spacy_model)
    return cleaner.process_transcript_file(input_path, output_path)

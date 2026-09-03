"""CPU model wrapper (spec: /models/local_extract.py).

Re-exports the ml.local_extract pipeline and adds an optional spaCy NER
refinement step: if `en_core_web_sm` (or SPACY_MODEL env) is installed, ORG/GPE
entities back-fill missing manufacturer/origin fields. Regex stays the baseline.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.local_extract import extract_label  # noqa: E402,F401


def spacy_refine(text: str, decl: dict) -> dict:
    """Fill manufacturer/origin gaps from spaCy NER. No-op when spaCy/model absent."""
    try:
        import spacy  # type: ignore

        model = os.environ.get("SPACY_MODEL", "en_core_web_sm")
        nlp = spacy.load(model)
        ents = {(e.label_, e.text) for e in nlp(text).get_ents() if hasattr(nlp(text), "get_ents")} \
            if False else [(e.label_, e.text) for e in nlp(text).ents]
        for label, value in ents:
            if label == "ORG" and not decl.get("manufacturer_name"):
                decl["manufacturer_name"] = value[:160]
            if label == "GPE" and not decl.get("country_of_origin"):
                decl["country_of_origin"] = value[:60]
        return decl
    except Exception:
        return decl


def extract_label_with_ner(image_bytes: bytes, ppm: float | None = None) -> dict:
    out = extract_label(image_bytes, ppm=ppm)
    out["declaration"] = spacy_refine(out["text"], out["declaration"])
    return out

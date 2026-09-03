# models/

CPU-only model artifacts and wrappers (no GPU builds, no torch required):

- `local_extract.py` — inference wrapper: `extract_label_with_ner()` = OpenCV +
  Tesseract + regex baseline, spaCy NER refinement only when a model is installed.
- `regex_rules.json` — versioned regex rule definitions (mirrors the backend baseline).
- Optional super-resolution models (`ESPCN_x2.pb` / `FSRCNN_x2.pb`, OpenCV
  `dnn_superres` format) may be dropped into this folder to enable the micro-text
  SR path in `app/services/vision.py`. They are intentionally NOT committed
  (large binaries); without them the pipeline uses 2x cubic upscaling.

spaCy (optional, CPU): `pip install spacy && python -m spacy download en_core_web_sm`
then `SPACY_MODEL=en_core_web_sm` (default).

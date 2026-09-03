# DELEGATION-ADDENDUM.md
## Required additions to DELEGATION.md (100% Local CPU Execution version)

Hand this file to the agent together with DELEGATION.md. It fills gaps that were established
and verified in earlier project work but are missing from the current DELEGATION.md. Treat
every section below as amending the phase/section it references — not optional extras.

---

## A. Amends Phase 2 — the core safety principle DELEGATION.md is missing

Add this as an explicit, load-bearing requirement of Phase 2, stated to the agent verbatim:

> A rule that could not run must never look like a rule that passed. If the spatial calibration
> pipeline returns no measurable height (e.g., no reference object was in frame), the font-size
> rule must return a distinct `NOT_ASSESSABLE` status — never silently `PASS`. Reporting a
> possibly-undersized label as compliant is the dangerous direction of error for a compliance
> tool and must be structurally impossible, not just avoided by convention.

Required status model for every rule outcome:

```python
class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_FOUND = "NOT_FOUND"          # declaration absent from the label
    NOT_ASSESSABLE = "NOT_ASSESSABLE"  # rule could not run (e.g. uncalibrated image)
```

Each outcome should carry: `rule_id`, `status`, `message`, `field`, `citation`,
`citation_verified: bool`, `observed`, `expected`, `severity`, plus a remedy hint for
`NOT_ASSESSABLE` cases (e.g. "place a reference object in frame to measure text height").

**Known bug class to guard against explicitly**: OCR confidence typically exists on two
different scales in a pipeline like this — the extractor/regex confidence (0.0–1.0) and the
raw Tesseract/EasyOCR line confidence (0–100). The legibility check (<60% threshold) must be
asserted against the correct scale. Conflating them makes the threshold fire almost always or
almost never, silently. Add a regression test that pins which scale `ocr_confidence` uses on
the extracted-field data structure, so a future refactor can't silently swap it.

---

## B. Amends Phase 2 — verified Legal Metrology Rule 7 text (replaces the placeholder numbers)

DELEGATION.md's Phase 2 currently says "e.g., 1mm, 2mm, 4mm standards" — replace this
placeholder with the actual verified rule text (sourced directly from the official Rules PDF,
see Section D below). This is not an approximation — it is the real Rule 7(2)/7(3) text:

**Rule 7(3) — letter height** (flat, not tiered): letters must be at least **1mm** in height;
when blown, formed, molded, embossed or perforated, at least **2mm**.

**Rule 7(3) — width ratio** (currently entirely unimplemented, must be added): letter/numeral
width must be at least **one-third of its height**, except for the numeral "1" and the letters
i, I, l.

**Rule 7(2) — numeral height**, tiered by declaration type:

*Table-I — when net quantity is declared by weight or volume:*

| Net quantity | Normal minimum height | Embossed/molded minimum height |
|---|---|---|
| Up to 200g/ml | 1mm | 2mm |
| 200g/ml – 500g/ml | 2mm | 4mm |
| Above 500g/ml | 4mm | 6mm |

*Table-II — when net quantity is declared by length, area, or number (tiered by principal
display panel area):*

| Panel area | Normal minimum | Embossed/molded minimum |
|---|---|---|
| Up to 100 cm² | 1mm | 2mm |
| 100–500 cm² | 2mm | 4mm |
| 500–2500 cm² | 4mm | 6mm |
| Above 2500 cm² | 6mm | 6mm |

Implementation note: numeral height and letter height are **separate checks** — do not
conflate them into one flat threshold. Numeral height is tiered (Table-I or Table-II,
depending on how the package's quantity is declared); letter height is flat (1mm/2mm) per
Rule 7(3). Encode both, plus the width-ratio rule, as named constants with a comment citing
the exact table/sub-rule — not scattered magic numbers.

---

## C. Amends Phase 2 — citation honesty

Every rule's `citation` field must reference the specific rule/sub-rule/table it implements.
Every rule starts with `citation_verified: False` **except** Rule 7 (font size/legibility),
which can be set `citation_verified: True` — its text has been directly confirmed against
the official Gazette PDF (Section D). All other rules (presence checks, MRP format, date
format, consumer care format) remain `citation_verified: False` until similarly confirmed.

`docs/rule-mapping.md` must lead with a note: citations were transcribed from the project's
verified legal source where marked `Verified: YES`, and from the original hackathon problem
statement's general description where marked `Verified: NO` — the unverified ones need a
further legal check before this tool is used for real enforcement, not just a hackathon demo.

---

## D. New — official legal source documents (add to repo layout)

Add a new folder: `docs/legal-source/`. Download and place these two PDFs there (do this
yourself before the agent starts, or ask the agent to fetch them — the second one is
sometimes blocked for automated fetches, so a manual browser download may be needed):

1. Primary — full official Rules 2011 text, confirmed accessible:
   `https://wbconsumers.gov.in/writereaddata/ACT%20&%20RULES/Act%20&%20Rules/9%20The%20Legal%20Metrology%20(Package%20Commodities)%20Rules,%202011.pdf`
2. Backup mirror:
   `https://megweights.gov.in/acts/Legal-Metrology-Packaged-Commodities-Rules-2011.pdf`

Instruct the agent: **read these directly using the PDF-reading skill/tooling, not by trying
to fetch the original consumeraffairs.gov.in site** (that domain blocks automated access).
Cross-check every implemented rule against this text before finalizing Phase 2, and update
`citation_verified` flags accordingly, with page/rule references in `rule-mapping.md`.

---

## E. Amends Phase 3 — data volume target and real-data merge step

DELEGATION.md's Phase 3 says "produce synthetic training data locally for testing" with no
scale target — given the requirement that this model needs strong real-world accuracy (this
will be used by the public), that's insufficient. Add:

- [ ] Generate at least **20,000–50,000 synthetic labeled samples** using
      `generate_synthetic_labels.py` (already fast and CPU-only — this is not a GPU-scale
      constraint, just a data-volume one). Include both positive and violation examples (the
      script already generates missing-field and undersized-font cases — use them).
- [ ] Leave an explicit, documented hook for merging in real annotated data
      (`real_train.jsonl`, produced later via the Label Studio pipeline —
      `label_studio_config.xml`, `run_ocr_for_labeling.py`, `convert_labelstudio_to_bio.py`,
      already present in `/ml/data_pipeline/` — do not rewrite these) via simple file
      concatenation before spaCy training.
- [ ] Report extraction accuracy (precision/recall/F1 per entity type) **split by data source**
      (synthetic vs. real) once any real data is merged in — do not report only a blended
      synthetic-heavy number as "the" accuracy. Log this in `docs/kaggle-workflow.md` or
      equivalently-named `docs/model-training.md` since there's no Kaggle step in this version.
- [ ] Record model metadata on every export: base spaCy model used, training date, sample
      counts (synthetic vs real), and eval scores — in a `model_metadata.json` alongside the
      exported pipeline, so every scan result can be traced back to exactly which model
      version produced it (important for an auditable compliance tool).

---

## F. Amends Phase 4 — human-in-the-loop before a report is finalized (recommended addition)

For a tool making legal-compliance judgments used by the public or by enforcement officers,
fully automated "final" violation reports are a real risk if the model or rule engine gets
something wrong. Add to Phase 4:

- [ ] Scan results are created with a status of `pending_review` by default.
- [ ] An authenticated officer/admin user must explicitly confirm or override each finding
      before a report is marked `final` and becomes exportable/shareable.
- [ ] The audit trail (who reviewed, when, any overrides) is stored alongside the scan record.

This can be scoped down for a hackathon demo (e.g., a single "Confirm & Generate Report"
button) but should exist even in minimal form — it's a meaningful, easy-to-explain feature for
judges, and the right default for anything resembling legal enforcement tooling.

---

## G. Repo layout addition

```
/docs
  legal-source/                # NEW — official Rules 2011 PDFs, ground truth for citations
    LMPC_Rules_2011.pdf
  architecture.md
  rule-mapping.md               # must lead with the verified/unverified citation note (Section C)
  model-training.md             # NEW — replaces the old "kaggle-workflow.md" naming; logs
                                 #        synthetic vs real accuracy split (Section E)
  deployment.md
```

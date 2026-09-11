# Model Training (CPU)

> Replaces the old `kaggle-workflow.md` naming — there is no Kaggle step in the
> CPU-local version. All training runs on a standard laptop CPU.

## Data

- **Synthetic** (`data/train/labels.jsonl`): 20,000–50,000 samples from
  `ml/data_pipeline/generate_synthetic_labels.py --count N --violation-rate 0.3 --no-images`.
  Includes positive AND violation examples (missing MRP / tax phrase / care /
  dates / net qty); the `truth.violation` field records which.
- **Real** (`data/real_train.jsonl`, optional): BIO rows converted from Label Studio
  via `ml/data_pipeline/convert_labelstudio_to_bio.py`. Same `{"text","bio"}` shape.
  Absent until officers annotate production labels — the trainer treats a missing
  file as "no real data yet", not an error.

## Training

```bash
python ml/train_ner.py --synthetic data/train/labels.jsonl --out models/lmpc_ner --iterations 10
python ml/train_ner.py --synthetic data/train/labels.jsonl --real data/real_train.jsonl --out models/lmpc_ner
```

Merge is plain concatenation; eval is a 10% per-source holdout.
`model_metadata.json` (base model, date, synthetic/real counts, per-source scores)
is written next to every export for auditability.

## Accuracy log (split by source — never blended-only)

| Date | Model | n_synth | n_real | Synth P/R/F1 | Real P/R/F1 | Notes |
|---|---|---|---|---|---|---|
| 2026-09-03 | regex baseline (no NER) | 5 | 0 | n/a (rules) | no data | Phase-1 gate: 6–7/7 fields, <1.2s/image |
| 2026-09-10 | extraction+layout (eval_real field acc.) | 15 photos | 7 backs, hand-labeled | 89/105 fields, 14/15 verdicts | 43/47 fields (91.5%) | A–F accuracy program; TrOCR/Gemini/VLM gated assists off in this number |
| 2026-09-11 | extraction v2, phone-photo set | 15 photos | 10 phone backs, hand-labeled (OFF set retired) | 89/105 fields, 14/15 verdicts | 38/69 fields (55.1%) | Real Indian labels: remaining misses are OCR-recall (ink-jet/scratched/vertical strips), not parser gaps; Gemini-vision probe recovers Suhana fully |
| — | `lmpc_ner` v1 | — | — | — | no real data yet | pending volume training run |

Fill the next row when the volume run completes. Do NOT report a blended
synthetic-heavy number as "the" accuracy.

## Real-label runbook (backs first — they carry the declarations)

Pre-labels are already generated (`data/prelabels_backs.jsonl`, 7 backs) and
converted to a one-click Label Studio import (`data/labelstudio_import.json`):

```bash
# 1. Regenerate any time new back photos arrive:
python ml/data_pipeline/run_ocr_for_labeling.py --indir data/real/backs --out data/prelabels_backs.jsonl
python ml/data_pipeline/prelabels_to_labelstudio.py --in data/prelabels_backs.jsonl \
    --out data/labelstudio_import.json --prefix data/real/backs
# 2. Label Studio: new project with ml/data_pipeline/label_studio_config.xml,
#    Import data/labelstudio_import.json, fix MRP/NET_QTY/MFG_DATE/EXP_DATE/
#    MANUFACTURER/CARE spans (aim: 50-100 backs), Export JSON annotations.
# 3. Convert + retrain (merge is plain concatenation; missing file = no real data):
python ml/data_pipeline/convert_labelstudio_to_bio.py --in annotations.json --out data/real_train.jsonl
python ml/train_ner.py --synthetic data/train/labels.jsonl --real data/real_train.jsonl \
    --out models/lmpc_ner --iterations 10
```

The merge path is probe-tested (18028 synthetic + sample real rows build one
training set). The backend picks up `models/lmpc_ner` on restart — no code
change needed. Log the new row above split by source.

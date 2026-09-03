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
| — | `lmpc_ner` v1 | — | — | — | no real data yet | pending volume training run |

Fill the next row when the volume run completes. Do NOT report a blended
synthetic-heavy number as "the" accuracy.

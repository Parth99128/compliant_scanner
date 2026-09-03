"""CPU spaCy NER training with synthetic + real data merge (addendum §E).

- Synthetic BIO is derived from generate_synthetic_labels.py ground truth.
- Real data hook: drop Label Studio-converted BIO rows at --real
  (default data/real_train.jsonl, same {"text","bio"} shape as
  convert_labelstudio_to_bio.py output). Merge is plain concatenation.
- Eval is reported SPLIT BY SOURCE (synthetic vs real), never blended only.
- Every export writes model_metadata.json (base model, date, counts, scores)
  so scans trace back to the exact model version.

    python ml/train_ner.py --synthetic data/train/labels.jsonl --out models/lmpc_ner
    python ml/train_ner.py --synthetic data/train/labels.jsonl --real data/real_train.jsonl \\
        --out models/lmpc_ner --iterations 10
    python ml/train_ner.py --dry-run   # build datasets + metadata skeleton, no training
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

ENTITY_PATTERNS = [
    ("MRP", re.compile(r"MRP\s*Rs\.?\s*[\d,]+(?:\.\d{1,2})?", re.IGNORECASE)),
    ("NET_QTY", re.compile(r"Net Qty:\s*[\d.,]+\s*(?:kg|g|mg|ml|l|pcs|cm)\b", re.IGNORECASE)),
    ("MFG_DATE", re.compile(r"Mfg:\s*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", re.IGNORECASE)),
    ("EXP_DATE", re.compile(r"Exp:\s*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", re.IGNORECASE)),
    ("MANUFACTURER", re.compile(r"^(?:.+?Foods|Shakti Home|Ganga Mills|Lotus Daily|Kisan Gold).*$", re.MULTILINE)),
    ("CARE", re.compile(r"Customer Care:\s*\S+.*?1800[\s\-]*\d[\d\s\-]*", re.IGNORECASE)),
]


def bio_from_lines(lines: list[str]) -> tuple[str, list[tuple[str, str]]]:
    text = "\n".join(lines)
    spans: list[tuple[int, int, str]] = []
    for label, pat in ENTITY_PATTERNS:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end(), label))
    toks = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    tags = ["O"] * len(toks)
    for s, e, lab in spans:
        first = True
        for i, (_, ts, te) in enumerate(toks):
            if te > s and ts < e and tags[i] == "O":
                tags[i] = f"B-{lab}" if first else f"I-{lab}"
                first = False
    return text, list(zip([t for t, _, _ in toks], tags))


def bio_to_char_spans(bio: list[list[str]]) -> tuple[str, list[tuple[int, int, str]]]:
    words = [w for w, _ in bio]
    text = " ".join(words)
    spans: list[tuple[int, int, str]] = []
    off = 0
    offsets: list[tuple[int, int]] = []
    for w in words:
        offsets.append((off, off + len(w)))
        off += len(w) + 1
    i = 0
    while i < len(bio):
        tag = bio[i][1]
        if tag.startswith("B-"):
            lab = tag[2:]
            j = i + 1
            while j < len(bio) and bio[j][1] == f"I-{lab}":
                j += 1
            spans.append((offsets[i][0], offsets[j - 1][1], lab))
            i = j
        else:
            i += 1
    return text, spans


def bio_spans(bio: list[list[str]]) -> set[tuple[int, int, str]]:
    """Token-index spans for eval comparison."""
    out: set[tuple[int, int, str]] = set()
    start: int | None = None
    lab: str | None = None
    for i, (_, tag) in enumerate(bio):
        if tag.startswith("B-"):
            if start is not None and lab:
                out.add((start, i, lab))
            start, lab = i, tag[2:]
        elif tag.startswith("I-") and start is not None and lab == tag[2:]:
            continue
        else:
            if start is not None and lab:
                out.add((start, i, lab))
            start, lab = None, None
    if start is not None and lab:
        out.add((start, len(bio), lab))
    return out


def prf(gold: list[set], pred: list[set]) -> dict:
    tp = sum(len(g & p) for g, p in zip(gold, pred))
    fp = sum(len(p - g) for g, p in zip(gold, pred))
    fn = sum(len(g - p) for g, p in zip(gold, pred))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3),
            "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
            "support": tp + fn}


def load_examples(synthetic: Path, real: Path | None) -> tuple[list[dict], list[dict]]:
    syn: list[dict] = []
    if synthetic.exists():
        for line in synthetic.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            text, bio = bio_from_lines(row["lines"])
            syn.append({"text": text, "bio": bio, "source": "synthetic"})
    real_ex: list[dict] = []
    if real and real.exists():
        for line in real.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            real_ex.append({"text": row["text"], "bio": [list(t) for t in row["bio"]], "source": "real"})
    return syn, real_ex


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", default="data/train/labels.jsonl")
    ap.add_argument("--real", default="data/real_train.jsonl")
    ap.add_argument("--out", default="models/lmpc_ner")
    ap.add_argument("--iterations", type=int, default=10)
    ap.add_argument("--eval-frac", type=float, default=0.1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    syn, real_ex = load_examples(Path(args.synthetic), Path(args.real))
    eval_sets: dict[str, list[dict]] = {"synthetic": [], "real": []}
    train: list[dict] = []
    for ex in syn + real_ex:
        (eval_sets[ex["source"]].append(ex) if random.random() < args.eval_frac else train.append(ex))
    print(f"train={len(train)} eval_synth={len(eval_sets['synthetic'])} eval_real={len(eval_sets['real'])}")

    out = Path(args.out)
    metadata = {
        "base_model": "spacy.blank('en')",
        "training_date": date.today().isoformat(),
        "n_synthetic": len(syn),
        "n_real": len(real_ex),
        "n_train": len(train),
        "iterations": 0 if args.dry_run else args.iterations,
        "eval": {},
    }
    if args.dry_run:
        (out / "model_metadata.json").parent.mkdir(parents=True, exist_ok=True)
        (out / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print("dry-run: datasets built, metadata skeleton written, no training")
        return 0

    try:
        import spacy  # type: ignore
        from spacy.training import Example  # type: ignore
        from spacy.util import minibatch  # type: ignore
    except ImportError:
        print("spaCy not installed — CPU training needs: pip install spacy", file=sys.stderr)
        return 2

    nlp = spacy.blank("en")
    ner = nlp.add_pipe("ner")
    for ex in train:
        for _, tag in ex["bio"]:
            if tag != "O":
                ner.add_label(tag[2:])
    optimizer = nlp.begin_training()
    for _ in range(args.iterations):
        random.shuffle(train)
        for batch in minibatch(train, size=32):
            examples = []
            for ex in batch:
                text, spans = bio_to_char_spans(ex["bio"])
                doc = nlp.make_doc(text)
                examples.append(Example.from_dict(doc, {"entities": spans}))
            nlp.update(examples, sgd=optimizer)
    # Eval split by source (never blended-only). Entity texts compared
    # (tokenization-independent) rather than token indices.
    eval_report: dict[str, dict] = {}
    for source, docs in eval_sets.items():
        gold, pred = [], []
        for d in docs:
            words = [w for w, _ in d["bio"]]
            g_spans = bio_spans(d["bio"])
            gold.append({" ".join(words[s:e]) + "|" + lab for s, e, lab in g_spans})
            doc = nlp(d["text"])
            pred.append({" ".join(e.text.split()) + "|" + e.label_ for e in doc.ents})
        eval_report[source] = prf(gold, pred) if docs else {"note": "no eval data for source"}
    metadata["eval"] = eval_report
    out.mkdir(parents=True, exist_ok=True)
    nlp.to_disk(out)
    (out / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(eval_report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

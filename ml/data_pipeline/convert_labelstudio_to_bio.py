"""Convert Label Studio NER export -> token BIO JSONL for spaCy training.

    python ml/data_pipeline/convert_labelstudio_to_bio.py --in annotations.json --out data/train_bio.jsonl
Expects Label Studio JSON with `text` and `label` spans (start/end/labels).
"""

from __future__ import annotations

import argparse
import json
import re


def to_bio(text: str, spans: list[dict]) -> list[tuple[str, str]]:
    toks = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    tags = ["O"] * len(toks)
    for sp in spans:
        s, e, labs = sp["start"], sp["end"], sp.get("labels", [])
        lab = labs[0] if labs else "ENT"
        first = True
        for i, (_, ts, te) in enumerate(toks):
            if te > s and ts < e:
                tags[i] = f"B-{lab}" if first else f"I-{lab}"
                first = False
    return [(t, tag) for (t, _, _), tag in zip(toks, tags)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    data = json.load(open(args.inp, encoding="utf-8"))
    n = 0
    with open(args.out, "w", encoding="utf-8") as fh:
        for task in data if isinstance(data, list) else [data]:
            text = task.get("text", "")
            spans = []
            for ann in task.get("annotations", []):
                for r in ann.get("result", []):
                    if r.get("type") == "labels":
                        spans.append({"start": r["value"]["start"], "end": r["value"]["end"],
                                      "labels": r["value"].get("labels", [])})
            fh.write(json.dumps({"text": text, "bio": to_bio(text, spans)}) + "\n")
            n += 1
    print(f"converted {n} tasks -> {args.out}")


if __name__ == "__main__":
    main()

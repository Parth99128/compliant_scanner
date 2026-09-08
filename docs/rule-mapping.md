# Rule Mapping — Legal Metrology (Packaged Commodities) Rules, 2011

> **Citation honesty note (DELEGATION-ADDENDUM §C):** citations marked
> **Verified: YES** were transcribed from the project's verified legal source
> (`docs/legal-source/LMPC-Rules-2011_WB-mirror.pdf`, Rule 7 on pp. 8–9).
> Citations marked **Verified: NO** come from the original hackathon problem
> statement's general description and need a further legal check before this
> tool is used for real enforcement — not just a hackathon demo.

| Check | Rule | Verified | Logic |
|---|---|---|---|
| `LMPC-6.1-manufacturer` | Rule 6(1)(a), PDF pp. 5–6 | YES | manufacturer name + address required |
| `LMPC-6.1-generic` | Rule 6(1)(b), PDF p. 5 | YES | generic/common name required |
| `LMPC-6.1-netqty` | Rule 6(1)(c), PDF p. 5 | YES | net qty > 0, SI/standard unit (g/kg/ml/l/mg/…) |
| `LMPC-6.1-mrp` | Rule 6(1)(e) + Rule 2(m) manner, PDF p. 3 + pp. 5–6 | YES | MRP > 0 and phrase "inclusive of all taxes" |
| `LMPC-6.1-dates` | Rule 6(1)(d) (month and year), PDF p. 5 | YES | mfg/pack/import month-year required; expiry > mfg |
| `LMPC-6.1-care` | Rule 6(1) consumer-care proviso (post-2011 amendment; absent from base text) | NO | consumer-care name/address/contact required |
| `LMPC-6.1-origin` | Rule 6(1)(a) importer clause, PDF p. 5 (PASS branch) / later amendment (import branch) | PARTIAL | imports must state country of origin |
| `LMPC-7.2-numeral` | Rule 7(2) Table-I/II ✅ verified | numeral height vs tier tables below |
| `LMPC-7.3-letter` | Rule 7(3) ✅ verified | letter height ≥ 1mm (≥ 2mm embossed/molded) |
| `LMPC-7.3-width` | Rule 7(3) proviso ✅ verified | glyph width ≥ 1/3 height (excl. `1`, `i`/`I`/`l`) |

Font height in mm = `pixel_height / PPM`, PPM from reference object (see `vision.py`).

## Rule 7 numeral tables (verified verbatim — `docs/legal-source/LMPC-Rules-2011_WB-mirror.pdf`, pp. 8–9)

Rule 7(2): numeral height minima follow **Table-I when net quantity is declared by
weight/volume**, **Table-II when declared by length/area/number**.

Table-I (weight/volume, by net quantity):

| Net quantity | Normal | Blown/formed/molded/embossed/perforated |
|---|---|---|
| Up to 200 g/ml | 1 mm | 2 mm |
| Above 200 g/ml up to 500 g/ml | 2 mm | 4 mm |
| Above 500 g/ml | 4 mm | 6 mm |

Table-II (length/area/number, by principal display panel area):

| Panel area | Normal | Blown/formed/… |
|---|---|---|
| Up to 100 cm² | 1 mm | 2 mm |
| Above 100 cm² up to 500 cm² | 2 mm | 4 mm |
| Above 500 cm² up to 2500 cm² | 4 mm | 6 mm |
| Above 2500 cm² | 6 mm | 6 mm |

Rule 7(3): letters ≥ 1mm (≥ 2mm when blown/formed/molded/embossed/perforated);
width of any letter/numeral ≥ one-third its height except `1`, `i`, `I`, `l`.
Table-II returns NOT_ASSESSABLE when panel area is unmeasured; all Rule 7 checks
return NOT_ASSESSABLE when the corresponding measurement is absent — never a
silent PASS (see `check_numeral_height` / `check_letter_height` / `check_width_ratio`).

## Failure guidance — a miss is not a violation

Every FAIL/NOT_FOUND outcome carries `cause` (`genuine | likely_genuine |
possible_miss | unmeasured`), a plain `why`, and ordered `next_steps`
(macro retake → OCR-text check → physical verification → Review action).
`NOT_FOUND` on a weak read (< 60% OCR confidence) is `possible_miss` and
folds the verdict to `INCOMPLETE`, never `NON_COMPLIANT` — the officer
verifies on the pack (confirm / correct / override) instead of the system
condemning a pack it could not read. See `backend/app/services/failure_guide.py`.

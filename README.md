# DrishtiLM — LMPC Compliance Scanner (SIH26034)

CPU-only Legal Metrology (Packaged Commodities) Rules, 2011 compliance scanner.
Phone photo in → OCR + extraction → deterministic rule engine → officer-reviewed report out.

## Quickstart

### Option A — Docker (backend + Postgres + web)

```powershell
cp .env.example .env
# Edit .env: set JWT_SECRET to a strong random value:
python -c "import secrets; print(secrets.token_hex(32))"
# Then:
docker compose up --build
```

- Backend Swagger: http://localhost:8000/docs
- Dashboard: http://localhost:3000
- Compose fails fast if `JWT_SECRET` is missing (by design — no default secrets in prod).

### Option B — Local backend (SQLite fallback)

```powershell
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # set JWT_SECRET, keep defaults for the rest
uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
```

Tesseract is optional: without it OCR degrades to empty-text + rule failures, never 500s.
Optional heavy engines stay off by default (`FLORENCE_ENABLED`, `TROCR_ENABLED`,
`VLM_ENABLED`, `LLM_PROVIDER=off`); enable only for experiments.

## Key API (prefix `/api/v1`)

- `GET /health` (public), `POST /auth/register|login` (rate-limited)
- `POST /validate` — typed declaration → compliance verdict, no OCR
- `POST /scans` (1 image) / `POST /scans/merge` (2–5 angles) → `202 Job` (poll `GET /jobs/{id}`) or inline `ScanOut` when `TESTING=1`
- `POST /scans/preview` — live viewfinder, no DB
- `GET /scans`, `GET /scans/{id}`, `PATCH /scans/{id}/product|fields|findings`
- `POST /scans/{id}/review` (`confirm` officer / `override` admin+notes) → `final`
- `GET /scans/{id}/report` (409 unless `final`), `POST /scans/{id}/explain`

Every response carries `X-Request-ID`; errors are `{detail, request_id}`.

## Safety model

- A rule that could not run never looks like a pass: uncalibrated font-size checks
  return `NOT_ASSESSABLE` with a remedy (place a reference object in frame).
- Statuses: `PASS | FAIL | NOT_FOUND | NOT_ASSESSABLE`; verdicts:
  `COMPLIANT | NON_COMPLIANT | INCOMPLETE`.
- OCR confidence is 0–100 (Tesseract scale); legibility warning at <60%.
- Nothing is `final` without officer confirm/override; overrides are audit-logged.

## Verify

```powershell
python ml/accept_phase1.py --count 5   # Phase-1 gate: 5/7 fields + font mm, <5s/image
python -m pytest tests -q              # from backend/
ruff check app tests; black --check app tests; python -m mypy app
npx tsc --noEmit                       # from web/
```

## Layout

- `backend/` FastAPI app (`app/api`, `app/services`, `app/models`, `tests/`)
- `ml/` CPU pipeline + `data_pipeline/` (synthetic + Label Studio + OFF fetchers)
- `models/` regex rules + spaCy `lmpc_ner` + `model_metadata.json`
- `web/` Next.js dashboard, `docs/` architecture/api-contract/rule-mapping/deployment/model-training
- `docs/legal-source/` official Rules 2011 PDF (ground truth for Rule 7 citations)

Rule 7 citations are verified against the Gazette mirror (`Verified: YES`);
other citations derive from the hackathon problem statement (`Verified: NO`) —
see `docs/rule-mapping.md` before any enforcement use.

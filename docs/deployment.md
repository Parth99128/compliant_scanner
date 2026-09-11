# Deployment

## Local (no Docker)

```
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # then set JWT_SECRET (see below)
uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
python -m pytest tests -q
```

SQLite (`scanner.db`) is the local fallback; `scanner.db*` and `.env` are git-ignored.

## Docker Compose (backend + Postgres + frontend)

```
cp .env.example .env   # set JWT_SECRET first — compose refuses to start without it
docker compose up --build
# backend http://localhost:8000/docs, dashboard http://localhost:3000
```

`backend` uses `env_file: .env` plus required `${JWT_SECRET:?...}` interpolation;
`DATABASE_URL` defaults to Postgres via `POSTGRES_PASSWORD` (default `scanner` is
fine for local demo only — change it for anything shared).

## Secrets

- `JWT_SECRET` (required): `python -c "import secrets; print(secrets.token_hex(32))"`.
  The backend also refuses insecure defaults when `ENVIRONMENT=production`
  (`backend/app/core/config.py`).
- `POSTGRES_PASSWORD`: change for non-local deploys; `DATABASE_URL` picks it up.
- `GEMINI_API_KEY`: only needed for `LLM_PROVIDER=gemini|gemma` explanations/fill;
  core pipeline never needs a key. Never commit `.env`.
- Rotate any key that was ever pasted into chat/logs or committed.

## Optional engines (all off by default)

| Flag | Cost on first use |
|---|---|
| `FLORENCE_ENABLED` (`Florence-2-base`) | ~1.5 GB download, ~30 s/scan CPU |
| `TROCR_ENABLED` (`trocr-small-printed`) | ~0.4 GB, seconds per weak row |
| `VLM_ENABLED` (`SmolVLM-256M`) | ~0.5 GB, 30–60 s/scan |
| `LLM_PROVIDER=gemini\|gemma` | billed per call, gated to weak reads |

`ml/accept_phase1.py` forces all of these off so the Phase-1 gate tests the
hermetic CPU baseline. Tesseract is optional inside the image; without it OCR
degrades to empty-text + rule failures rather than 500s.

## Production notes

- Set `ENVIRONMENT=production`, strong `JWT_SECRET`, real `POSTGRES_PASSWORD`.
- Put the stack behind TLS; `CORS` origins live in `backend/app/core/config.py`.
- Health: `GET /api/v1/health` (returns `request_id`); logs are JSON via structlog.
- Rate limits: `POST /scans` 20/min, `register` 10/min (disabled when `TESTING=1`).

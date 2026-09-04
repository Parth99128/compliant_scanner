# Deployment

## Local (no docker)
```
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # or set DATABASE_URL, JWT_SECRET
uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
pytest
```

## Docker Compose (backend + postgres + frontend)
```
docker compose up --build
# backend http://localhost:8000/docs, dashboard http://localhost:3000
```

Env vars: `DATABASE_URL`, `JWT_SECRET`, `MAX_UPLOAD_MB`, `CLOUD_VISION_ENABLED`.
Tesseract is optional inside the image; OCR degrades to empty-text + rule failures rather than 500s.

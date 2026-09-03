# LMPC Scanner — Architecture (CPU-only)

```
[React frontend] --POST /api/v1/scans--> [FastAPI backend]
                                                |
                       +------------------------+------------------------+
                       |                        |                        |
                  vision.py                ocr.py / extraction.py     rule_engine.py
               (OpenCV deskew,            (Tesseract CPU primary,       (deterministic
                denoise, upscale,          Florence-2 VLM second        Legal Metrology
                PPM font-height)           opinion when enabled,         checks)
                                           regex + optional spaCy,
                                           Cloud Vision stub)
                                                |
                                         [PostgreSQL via SQLAlchemy]
```

- `request_id` generated per request (middleware), propagated in logs + `X-Request-ID` header.
- Uploads validated (type/size); OCR and image steps never raise — structured 4xx/5xx JSON.
- Auth: bcrypt + JWT bearer for `/scans`; `/health` and `/validate` public.
- DB: PostgreSQL in compose; SQLite fallback for local dev/tests via `DATABASE_URL`.
- No GPU anywhere: opencv-headless + Tesseract CPU + regex. Torch/EasyOCR optional, not required.

# API Contract (v1, prefix `/api/v1`)

- `GET /health` → `{status, request_id}`
- `POST /auth/register {username, password, role=officer|admin}` → `{access_token, token_type}` (10/min)
- `POST /auth/login` → same (20/min)
- `POST /validate` (DeclarationIn JSON) → `ComplianceOut {compliant, results[{rule_id, passed, message}], warnings[], request_id}`
- `POST /scans` (multipart `file` + optional form `ppm`, `font_px`, `letter_px`, `panel_area_cm2`, `is_embossed`; Bearer required, 20/min) → `ScanOut {id, request_id, ocr_engine, ocr_text, ocr_confidence, font_height_mm, compliant, results, warnings, boxes[{text,x,y,w,h,confidence}]}`
- `GET /scans` (Bearer; own scans, admin sees all) → `ScanSummaryOut[]`
- `GET /scans/{id}` (owner/admin) → `ScanOut`
- `GET /scans/{id}/report` (owner/admin) → `application/pdf` download
- `POST /scans/{id}/explain` (owner/admin, 10/min) → `ExplainOut {explanation, provider, model}`; optional Gemini, off by default (`LLM_PROVIDER=gemini` + `GEMINI_API_KEY` in `.env`); 409 when disabled, 502 on provider failure

Errors: `{detail, request_id}` with 400/401/403/404/409/413/415/422/429/500/502.
Full OpenAPI/Swagger at `/docs` when server runs.

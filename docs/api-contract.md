# API Contract (v1, prefix `/api/v1`)

- `GET /health` → `{status, request_id}`
- `POST /auth/register {username, password, role=officer|admin}` → `{access_token, token_type}` (10/min)
- `POST /auth/login` → same (20/min)
- `POST /validate` (DeclarationIn JSON) → `ComplianceOut {compliant, results[{rule_id, passed, message}], warnings[], request_id}`
- `POST /scans` (multipart `file` + optional form `ppm`, `font_px`, `letter_px`, `panel_area_cm2`, `is_embossed`; Bearer required, 20/min) → `ScanOut {id, request_id, ocr_engine, ocr_text, ocr_confidence, font_height_mm, compliant, results, warnings, boxes[{text,x,y,w,h,confidence}]}`
- `POST /scans/merge` (multipart `files` ×2–5 of the same label + same optional form fields; Bearer, 10/min) → one `ScanOut`: OCR lines unioned by confidence across angles, extracted + evaluated once, measurements from the best frame, engine tagged `+mergeN`
- `GET /scans` (Bearer; own scans, admin sees all; `?q=&verdict=&status=`) → `ScanSummaryOut[]` (each adds `preview`, `product_name`, `brand_name`, `category`, `has_image`; product auto-filled from extraction, overridable at upload)
- `PATCH /scans/{id}/product` (owner/admin) `{product_name, brand_name, category}` → `ScanOut`
- `GET /stats/overview` (Bearer; scoped to role) → `{total, by_verdict, top_failed_rules, by_day, recent}`
- `GET /scans/{id}` (owner/admin) → `ScanOut` (adds `has_image`, `coord_w/h`: OCR box space; `boxes[]` now persisted)
- `GET /scans/{id}/image` (owner/admin) → downscaled `image/jpeg` capture for the viewer (404 when absent)
- `GET /scans/{id}/report` (owner/admin) → `application/pdf` download
- `POST /scans/{id}/explain` (owner/admin, 10/min) → `ExplainOut {explanation, provider, model}`; optional Gemini, off by default (`LLM_PROVIDER=gemini` + `GEMINI_API_KEY` in `.env`); 409 when disabled, 502 on provider failure
- `POST /scans/preview` (multipart `file` viewfinder frame + optional `ppm`, `panel_area_cm2`, `is_embossed`; Bearer, 30/min) → `ScanPreviewOut {ocr_engine, ocr_text, ocr_confidence, word_count, font_height_mm, ppm_used, sharpness, fields_found{generic,manufacturer,net_qty,mrp,mfg_date,care}, fields_count, verdict, ready, ready_reason, boxes[], coord_w/h}`; no DB write — live-camera text + size check for auto-capture

Errors: `{detail, request_id}` with 400/401/403/404/409/413/415/422/429/500/502.
Full OpenAPI/Swagger at `/docs` when server runs.

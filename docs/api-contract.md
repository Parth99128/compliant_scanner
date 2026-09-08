# API Contract (v1, prefix `/api/v1`)

- `GET /health` → `{status, request_id}`
- `POST /auth/register {username, password, role=officer|admin}` → `{access_token, token_type}` (10/min)
- `POST /auth/login` → same (20/min)
- `POST /validate` (DeclarationIn JSON) → `ComplianceOut {compliant, results[{rule_id, passed, message}], warnings[], request_id}`
- `POST /scans` (multipart `file` + optional form `ppm`, `font_px`, `letter_px`, `panel_area_cm2`, `is_embossed`, `product_name`, `brand_name`, `category`, `scan_lat`, `scan_lon`; Bearer required, 20/min) → `202 JobOut {job_id, status, kind, frames_total}` in production (poll `GET /jobs/{id}` to `done` → `scan_id`); same worker inline with `200 ScanOut` under `TESTING=1`
- `POST /scans/merge` (multipart `files` ×2–5 + same form fields; Bearer, 10/min) → same 202/job contract; text unioned by confidence, measurements from the best calibrated frame
- `GET /jobs/{job_id}` (owner/admin) → `JobOut`; async analysis never holds HTTP open (VPNs/proxies can't reap it)
- `GET /scans` (Bearer; own scans, admin sees all; `?q=&verdict=&status=`) → `ScanSummaryOut[]` (each adds `preview`, `product_name`, `brand_name`, `category`, `has_image`; product auto-filled from extraction, overridable at upload)
- `PATCH /scans/{id}/product` (owner/admin) `{product_name, brand_name, category}` → `ScanOut`
- `PATCH /scans/{id}/fields` (owner/admin, partial Rule 6 JSON: maker/generic/qty/mrp/dates/care/origin/imported/panel area; machine-measured sizes ignored) → re-evaluated `ScanOut` with `corrected_by/at` audit + auto-synced product identity
- `PATCH /scans/{id}/findings` (owner/admin, `{rule_id, observed?, present?}`; Rule 6 only) → per-finding attestation overlay (no engine re-run): text/Present attests PASS with `manual` flag, uncheck reverts or disputes; verdict refolded, machine rows pristine
- `GET /stats/overview` (Bearer; scoped to role) → `{total, by_verdict, top_failed_rules, by_day, recent}`
- `GET /scans/{id}` (owner/admin) → `ScanOut` (adds `has_image`, `coord_w/h`: OCR box space; `boxes[]` now persisted; `frames[]`: every uploaded angle `{index, is_best, measured, url, ocr_confidence, word_count, words_added, boxes[], coord_w/h}`; `measured_index`: angle Rule 7 was measured on — strongest read among calibrated frames)
- `GET /scans/{id}/image` (owner/admin) → downscaled `image/jpeg` capture for the viewer (best frame; 404 when absent)
- `GET /scans/{id}/images` (owner/admin) → `FrameOut[]` gallery of all uploaded angles in upload order
- `GET /scans/{id}/image/{frame_index}` (owner/admin) → `image/jpeg` for one non-best merge angle (404 when absent)
- `GET /scans/{id}/report` (owner/admin) → `application/pdf` download
- `POST /scans/{id}/explain` (owner/admin, 10/min) → `ExplainOut {explanation, provider, model}`; optional Gemini, off by default (`LLM_PROVIDER=gemini` + `GEMINI_API_KEY` in `.env`); 409 when disabled, 502 on provider failure
- `POST /scans/preview` (multipart `file` viewfinder frame + optional `ppm`, `panel_area_cm2`, `is_embossed`; Bearer, 30/min) → `ScanPreviewOut {ocr_engine, ocr_text, ocr_confidence, word_count, font_height_mm, ppm_used, sharpness, fields_found{generic,manufacturer,net_qty,mrp,mfg_date,care}, fields_count, verdict, ready, ready_reason, boxes[], coord_w/h}`; no DB write — live-camera text + size check for auto-capture

Errors: `{detail, request_id}` with 400/401/403/404/409/413/415/422/429/500/502.
Full OpenAPI/Swagger at `/docs` when server runs.

## Failure guidance (every non-PASS result)

Each result carries `cause` (`""` on PASS, else `genuine | likely_genuine |
possible_miss | unmeasured | attested | disputed`), a plain-language `why`,
and ordered `next_steps[]` (retake macro → check OCR text → verify on the
physical pack → Review confirm/correct/override). Shown in the UI rule cards
and the PDF findings table.

A miss is not a violation: `NOT_FOUND` outcomes on a weak read (OCR
confidence < 60%) are `possible_miss` and fold the verdict to `INCOMPLETE`
(verify, don't condemn) — unless a genuine breach is also present, which
keeps `NON_COMPLIANT`. Typed `/validate` input (no OCR) keeps the strict
verdict. Officer attestation clears stale guidance (`attested`) or marks
disputes (`disputed`).

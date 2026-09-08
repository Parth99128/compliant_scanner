# Our Tech Stack — in Simple Words

Goal: an officer opens the app on an ordinary laptop in a market, scans a pack in under 5 seconds, with no costly GPU and no paid cloud API. All AI runs on the same machine via Docker.

Honest note: the AI pipeline itself needs no internet. But the web page currently needs a live connection to that local backend (localhost or same Wi-Fi). There is no offline queue yet — if the backend is stopped, upload shows Cannot reach the API server. Full offline PWA with queued scans is roadmap, not present today.

## 1. App screen — Next.js 16 + React 19 + Tailwind

What: the website the officer clicks. Photo upload, guided camera, dashboard, history search, PDF download. It talks to the backend over fetch and shows Cannot reach the API server if the backend is down.

Why: one codebase works on phone and laptop. It gives login pages, tables and charts out of the box, so we did not build two apps.

Alternate: Streamlit is popular in hackathons, but it has no proper login, no clean routing, and looks like a demo. A separate React Native mobile app would double our work for no gain, since a mobile browser is enough.

Not yet: no service worker, no manifest, no IndexedDB outbox. So airplane-mode capture that syncs later does not work today.

## 2. Server — FastAPI + Pydantic

What: the brain behind the screen. Receives the photo at POST /api/v1/scans, runs vision + rules, saves to database.

Why: FastAPI is Python, so the same team writes AI and server. It checks every input automatically, creates live API docs at /docs for judges to try, and tags every scan with a request_id for tracing.

Alternate: Django is too heavy for a single-purpose scanner. Plain Flask gives no type checking or docs. Node Express would force two languages for no benefit.

## 3. Photo cleaning + measurement — OpenCV + NumPy

What: straightens tilted photos, removes glare and shadow, sharpens small text, and measures real font height. We place an 85.6 mm card next to the pack once, get pixels-per-mm, then font_mm = pixels / PPM.

Why: Rule 7 of the 2011 Rules punishes small fonts in millimetres, not pixels. Without this step font checking is impossible. OpenCV runs fully on CPU with no internet.

Alternate: PIL alone can resize but cannot deskew or measure. GPU super-resolution looks nice in papers but SIH laptops have no GPU, so we use light ESPCN with cubic fallback.

## 4. Reading words — Tesseract first, Florence-2 only when stuck

What: Tesseract reads every printed word with boxes and a confidence score. If confidence is below 60 percent or the pack is shiny, Florence-2 gives a second opinion.

Why: Tesseract is free, runs on the laptop with no cloud call, fast on CPU, and tells us when it is unsure. That honesty lets us say INCOMPLETE instead of guessing. Florence-2 stays optional so normal packs stay fast.

Alternate: Google Cloud Vision or Gemini-only needs internet, costs money per scan, and sends legal evidence outside the laptop. EasyOCR is accurate but much slower on CPU.

## 5. Finding the 7 details — Regex + spaCy + RapidFuzz

What: turns raw words into price, weight, dates, maker address, product name, helpline and origin. Regex catches fixed patterns like Rs and JAN 2025. spaCy reads messy addresses. RapidFuzz tolerates brand spelling mistakes.

Why: labels in India are irregular. Pure patterns break, pure AI hallucinates. The hybrid runs on the backend with no external API call, and is fast and testable.

Alternate: regex alone fails on multi-line addresses. An LLM alone is slow, invents prices, and cannot guarantee the same output twice.

## 6. Law check — plain Python, no AI guessing

What: 10 checks coded exactly from the 2011 Rules. Rule 6 checks presence of declarations. Rule 7 checks numeral tables 1/2/4/6 mm, letters above 1 mm, width above one-third height. Result is COMPLIANT, NON_COMPLIANT or INCOMPLETE with cause, plain reason and next steps.

Why: a court needs the same input to always give the same verdict with a clause number. Only deterministic code does that.

Alternate: asking an LLM is this compliant is non-deterministic and cannot cite Rule 6(1)(c) reliably.

## 7. Report — ReportLab PDF + JSON/CSV

What: one-tap court-ready PDF with photos and violations, plus editable JSON/CSV for records.

Why: the problem statement demands both PDF and editable. ReportLab runs inside the backend with no cloud call and full control of layout.

Alternate: browser print to PDF looks different on every machine. Cloud PDF services fail offline.

## 8. Memory — PostgreSQL 16, SQLite for local dev

What: stores every scan, photo, verdict and officer action. Powers history, search and trend charts.

Why: enforcement needs audit. SQL gives reliable search by brand, date and violation. Docker gives Postgres in one command, SQLite lets a developer run tests without setup.

Alternate: Mongo or Firebase add complexity with no benefit for tabular inspection data. SQLite alone cannot serve multiple officers.

## 9. Running + quality — Docker Compose + pytest + mypy + ruff

What: docker compose up --build starts web, server and database together. Every push runs tests for blurred photos, missing fields and corrupt uploads.

Why: judges run one command and it works. Tests prove we handle field failures gracefully.

Alternate: manual pip install steps always break on stage. No tests means a blurry photo crashes the demo.

Golden rule across all layers: if the photo cannot be measured, the system says INCOMPLETE and asks for a macro retake. It never calls it passed. Nothing becomes final without officer OK.

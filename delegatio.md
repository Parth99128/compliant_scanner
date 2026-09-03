# DELEGATION.md
## Project: Legal Metrology Packaged Commodities Compliance Scanner (SIH26034)
## Compute model: 100% Local CPU Execution (Intel Core Ultra 5 / Standard Laptop CPU)

This file is written to be handed directly to a local coding agent (OpenCode, Claude Code, Cursor, Aider, etc.).
The agent runs on your local machine and writes, tests, and runs all code locally on CPU. No remote GPU clusters, Kaggle notebooks, or external training pipelines are used.

---

## 0. Mission statement (give this to the agent verbatim)

> Your environment is a standard CPU-only laptop with no dedicated GPU. Your job is to build this project locally end-to-end to an **industry-ready standard** (see Section 1 — tested, secure, logged, documented, containerized).
>
> You will implement a high-efficiency CPU pipeline: OpenCV preprocessing for image deskewing and super-resolution, light CPU-based OCR (Tesseract / EasyOCR CPU) combined with lightweight NLP (spaCy / Regex) or optional Cloud Vision API fallback wrappers, a deterministic Legal Metrology rule engine, a FastAPI backend, a React/React Native frontend, and a PostgreSQL database. Work through the phases below in order. A phase is only "done" when both its acceptance criteria AND the Section 1 quality bar are met.

---

## 1. Quality bar: Industry-Ready Engineering

Every phase must be built to production standards:

- **Testing**: Real unit and integration tests (PyTest) for the rule engine, extraction logic, and API endpoints. Target edge cases (missing fields, blurred labels, corrupted OCR output, unauthorized requests).
- **Error handling**: Every external call (OCR, DB, file upload, image processing) must handle failure gracefully. Return structured JSON error responses with standard HTTP status codes.
- **Input validation & security**: Validate file types/sizes on upload, sanitize inputs, use parameterized queries (SQLAlchemy ORM), hash passwords (bcrypt), and rate-limit sensitive endpoints. Never hardcode secrets.
- **Config & secrets**: All credentials (DB URL, JWT secret, API keys) managed via environment variables and `.env` (git-ignored). Provide `.env.example`.
- **Logging & observability**: Structured JSON logging (using Python `structlog`) in backend and inference pipelines. Assign a unique `request_id` to every scan.
- **Code quality**: Full Python type hints (`mypy`), linting (`ruff`/`flake8`), and formatting (`black`).
- **API design**: Versioned API (`/api/v1/...`), auto-generated OpenAPI/Swagger documentation with explicit Pydantic schemas.
- **Containerization**: Dockerfile for backend and frontend, plus a `docker-compose.yml` wiring backend, PostgreSQL, and frontend for single-command startup.
- **CI**: GitHub Actions workflow running linting and test suites on every push/PR.
- **Documentation**: Provide `/docs/architecture.md`, `/docs/api-contract.md`, `/docs/rule-mapping.md`, and `/docs/deployment.md`.

---

## 2. Architecture & CPU Execution Strategy

To achieve sub-second execution without a local GPU:

1. **OCR Layer**: Run Tesseract OCR or EasyOCR in CPU-only mode. Preprocess low-res text using lightweight OpenCV image filters (binarization, sharpening, super-resolution).
2. **Extraction Engine**: Use a hybrid regex + spaCy NER pipeline for field parsing (MRP, Net Qty, Dates, Address). Provide an optional adapter pattern for Google Cloud Vision / Gemini API for complex labels.
3. **Spatial Calibration Engine**: Use OpenCV to detect physical target objects (e.g., standard reference dimensions) to compute the Pixel-Per-Millimeter (PPM) ratio to measure label font height in physical millimeters.
4. **Rule Engine**: Pure Python deterministic logic enforcing the Legal Metrology (Packaged Commodities) Rules, 2011.

---

## 3. Repository Layout

/backend            # FastAPI app — rule engine, spatial calibration, DB, auth, PDF report gen
/frontend           # React / React Native UI (upload, smart camera overlays, dashboard, history)
/ml
/data_pipeline    # Pre-built synthetic generator and dataset converters
generate_synthetic_labels.py
label_studio_config.xml
run_ocr_for_labeling.py
convert_labelstudio_to_bio.py
/data             # Local JSONL datasets & sample label images
/models           # Lightweight CPU spaCy NER pipelines and regex rule definitions
local_extract.py  # CPU inference wrapper (Regex baseline + spaCy CPU pipeline)
/docs
architecture.md
rule-mapping.md
deployment.md
DELEGATION.md
README.md
docker-compose.yml


---

## 4. Build Phases

### Phase 1 — CPU Extraction Baseline & Spatial Calibration
- [ ] Implement `/ml/local_extract.py`: OpenCV image enhancement + Tesseract/EasyOCR in CPU mode + Regex extraction for core mandatory fields.
- [ ] **Micro-text Super Resolution**: Use OpenCV `dnn_superres` (ESPCN or FSRCNN lightweight models) to sharpen sub-millimeter label text before feeding to OCR.
- [ ] **Spatial Calibration**: Implement an OpenCV script that calculates the Pixel-Per-Millimeter (PPM) ratio from a reference marker (e.g., standard alignment stencil) and measures the physical height (mm) of text bounding boxes.
- **Acceptance**: Extract 5/7 fields on sample images AND output calculated physical font height in millimeters on CPU in under 5 seconds per image.

### Phase 2 — Rule Engine (Legal Metrology 2011)
- [ ] Implement isolated rule functions mapped to Legal Metrology (Packaged Commodities) Rules, 2011 clauses (MRP syntax, Net Quantity units, Date formatting, Manufacturer details, Consumer Care details).
- [ ] **Font Size & Legibility Check**: Match calculated bounding box mm heights against Rule 7 minimum font size tables (e.g., 1mm, 2mm, 4mm standards based on net volume/weight). Flag low OCR confidence (<60%) as a legibility warning.
- **Acceptance**: PyTest suite validating pass/fail/missing rules for both text data syntax and physical font dimensions.

### Phase 3 — Local NLP Field Extractor & Synthetic Pipeline
- [ ] Use `/ml/data_pipeline/generate_synthetic_labels.py` to produce synthetic training data locally for testing.
- [ ] Build a lightweight CPU spaCy Named Entity Recognition (NER) model fine-tuned locally or configure a fallback wrapper for external cloud vision parsing.
- [ ] Integrate `local_extract.py` to seamlessly combine OCR output, spaCy entity parsing, and Regex logic.
- **Acceptance**: Field extractor handles irregular address layouts and non-standard date formats with higher precision than raw regex, running entirely on CPU.

### Phase 4 — Backend API, Auth & Report Generator
- [ ] FastAPI Application setup with JWT authentication and role-based access (Officer, Admin).
- [ ] Endpoints:
  - `POST /api/v1/scans` (Accepts image upload + spatial calibration data → runs OCR, calibration, & rules → saves to DB).
  - `GET /api/v1/scans` & `GET /api/v1/scans/{id}` (Retrieves scan history and rule status).
  - `GET /api/v1/scans/{id}/report` (Generates printable PDF compliance report using ReportLab).
- **Acceptance**: Full round-trip API test: Upload image → process → save to PostgreSQL → generate downloadable PDF compliance summary.

### Phase 5 — Frontend & Smart Capture UI
- [ ] Web Dashboard & Mobile-friendly UI (React / React Native).
- [ ] **Smart Capture Interface**:
  - **Context vs Macro Flow**: Step 1 for full product view, Step 2 for close-up macro label capture.
  - **Calibration Overlay**: SVG stencil guides for aligning packaging and physical reference dimensions.
  - **Gyroscope Alignment**: Sensor integration warning user if phone angle creates severe perspective skew.
- [ ] Display annotated bounding boxes over scanned packaging with color-coded compliance tags (Green = Pass, Red = Violation).
- **Acceptance**: Working UI allowing user to capture/upload packaging photos, view live OCR bounding boxes with compliance tags, and download violation reports.

### Phase 6 — Production Hardening
- [ ] Package frontend, backend, and PostgreSQL database into `docker-compose.yml`.
- [ ] Configure GitHub Actions workflow for linting (`ruff`), typing (`mypy`), and testing (`pytest`).
- [ ] Add rate limiting (`slowapi`) and structured JSON logging (`structlog`) with unique trace IDs across all endpoints.
- **Acceptance**: Fresh clone executes cleanly via `docker-compose up` with zero manual configuration; CI passes completely.

### Phase 7 — Technical Documentation
- [ ] Author `/docs/architecture.md`, `/docs/rule-mapping.md`, and `/docs/deployment.md`.
- [ ] README detailing setup instructions, local API testing via Swagger UI (`/docs`), and single-command Docker deployment.

---

## 5. Execution Rules for Agent

- **Zero GPU Assumptions**: Do not write code that requires CUDA, PyTorch GPU builds, or external GPU execution environments.
- **CPU Optimization**: Keep batch sizes small, prefer lightweight ML models (spaCy `en_core_web_sm`, OpenCV CPU filters, Tesseract), and optimize image downsampling before processing.
- **Strict Phase Gatekeeper**: Do not move to the next phase until all unit tests and acceptance criteria for the current phase are validated.

---

## Appendix — Prompt for Coding Agent

```text
Read DELEGATION.md fully before writing any code. Note that this project runs 100% locally on a CPU-only laptop — do not use or configure GPU dependencies. 

Build the project phase by phase (Phases 1 through 7) adhering strictly to the Quality Bar in
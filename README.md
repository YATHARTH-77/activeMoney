# 📊 Activv Money — Self-Learning PMS & AIF Statement Intelligence Pipeline

> **Neuro-Symbolic Document Extraction Engine:** Multi-Provider LLM Spatial Compilation (`Groq` + `Gemini`) • Zero-LLM Deterministic Runtime • Multi-Page Finite State Machine • Strict `Decimal` Financial Reconciliation • Live Gmail IMAP Ingestion • Real-Time Operational Dashboard

---

## 1. Executive Summary & Architectural Thesis

Wealth management platforms in India ingest thousands of Portfolio Management Services (**PMS**) and Alternative Investment Fund (**AIF**) statements across dozens of wealth managers. These PDFs lack industry-wide formatting standards, vary wildly in spatial geometry, span multiple pages with interrupting footers, and silently change layouts over time (**Layout Drift**).

Standard industry approaches fail in two predictable ways:
1. **Pure Regex / Template Parsers** are brittle; a 5-pixel column shift or a new disclaimer footer breaks extraction or silently drops rows.
2. **Direct LLM Extraction** (sending every PDF to an LLM to read numbers) violates fintech economics and reliability: it is slow, expensive at scale, leaks client PII to third-party APIs on every run, and suffers from stochastic numeric hallucinations.

### The Activv Money Solution: LLM-as-Compiler ("The Golden Rule")
This system implements a **Self-Learning Neuro-Symbolic Architecture** governed by a strict operational invariant:

> **The Golden Rule:** *LLMs are never used to extract financial data in production. Instead, LLMs act strictly as a one-time spatial compiler that writes a declarative JSON extraction ruleset (`LayoutArtifact`). All data extraction is executed locally by a deterministic geometric engine.*

1. **Cold Start (Unseen Layout — 1 LLM Call):** When an unfamiliar statement layout arrives, the `LayoutFingerprinter` computes its structural signature. The `LearningOrchestrator` extracts a sanitized spatial coordinate map (`[Y:top] X:x0-x1 'token'`) across pages and invokes our **Multi-Provider LLM Router** (`Groq openai/gpt-oss-20b` Primary $\rightarrow$ `Google Gemini 3.8 Flash` Fallback) to synthesize a candidate `LayoutArtifact`.
2. **Mathematical Gatekeeping:** The candidate artifact is immediately tested on the document using the local `DeterministicParser`. The output is audited by the `FinancialValidator` ($\sum \text{Holdings} + \text{Cash} == \text{Closing Value}$).
3. **Promotion or Quarantine:** Only if the mathematical identity holds within `₹0.05` is the artifact promoted to `ACTIVE` in SQLite (`artifacts.db`). If every LLM provider fails to produce a mathematically balanced extraction, the artifact is marked `REJECTED` and the statement is safely routed to the **Human-in-the-Loop Quarantine Queue** (`statements.db`).
4. **Warm Runtime (Known Layout — 0 LLM Calls):** Every subsequent statement matching an `ACTIVE` layout fingerprint bypasses all LLM APIs completely, executing deterministically in milliseconds with zero external network calls.

---

## 2. End-to-End System Architecture

```text
+-----------------------------------------------------------------------------------+
|                        1. INGESTION & STAGING LAYER                               |
|  [Gmail Inbox (IMAP SSL)] ---> [EmailIngestor: RFC822 Parser]                     |
|                                   |-- %PDF- Magic-Byte Verification               |
|                                   |-- Path-Traversal Sanitization                 |
|                                   +-- SHA-256 Content-Addressed Staging           |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     2. STRUCTURAL FINGERPRINTING & ROUTING                        |
|  [pdfplumber Spatial Extractor] ---> [LayoutFingerprinter]                        |
|                                         |-- Masks dynamic dates, numbers & IDs    |
|                                         +-- Computes SHA-256 Structural Hash      |
+-----------------------------------------------------------------------------------+
                                          |
                       +------------------+------------------+
                       |                                     |
          [Hash Found in artifacts.db]          [Unknown Hash / Layout Drift]
          (WARM PATH: 0 LLM API Calls)          (COLD START: Self-Learning Loop)
                       |                                     |
                       |                                     v
                       |                       +------------------------------------+
                       |                       |   3. MULTI-PROVIDER LLM ROUTER     |
                       |                       |  Primary:  Groq (gpt-oss-20b)      |
                       |                       |  Fallback: Gemini (3.8-flash)      |
                       |                       |  Synthesizes Candidate JSON Rules  |
                       |                       +------------------------------------+
                       |                                     |
                       +------------------+------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                  4. INDUSTRIAL DETERMINISTIC PARSER ENGINE                        |
|  * Proximity Summary Scanner: Slices post-label line text to prevent Y-collisions |
|  * Multi-Page FSM: SEARCHING -> ACTIVE_TABLE -> TERMINATED across page breaks     |
|  * Center-of-Mass Projection: Maps word midpoints ((x0+x1)/2) to column bounds    |
|  * Fuzzy Column Resolver: Normalizes header synonyms (Scrip/Security/Valuation)   |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   5. FINANCIAL VALIDATION FORTRESS (Decimal)                      |
|  * Equation 1 (PMS): Sum(Holdings.market_value) + Summary.cash == Summary.closing |
|  * Equation 2 (Sanity): Opening >= 0, Closing >= 0, NAV > 0 (if applicable)       |
|  * Tolerance: Strict Decimal arithmetic within +/- 0.05 INR                       |
+-----------------------------------------------------------------------------------+
                                          |
                       +------------------+------------------+
                       |                                     |
                [Validation: PASS]                    [Validation: FAIL]
                       |                                     |
                       v                                     v
       +-------------------------------+     +-------------------------------+
       |  * Promote Artifact -> ACTIVE |     |  * Mark Artifact -> REJECTED  |
       |  * Save Verified Statement    |     |  * Route Statement ->         |
       |    to statements.db           |     |    Quarantine Queue           |
       +-------------------------------+     +-------------------------------+
                       \                                     /
                        +-----------------+-----------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|               6. OBSERVABILITY & OPERATOR PRESENTATION LAYER                      |
|  * Streamlit Executive Web UI (`scripts/dashboard.py`) with PII Compliance Shield |
|  * CLI Quarantine Inspector (`scripts/review.py list | view | resolve`)           |
+-----------------------------------------------------------------------------------+
```

---

## 3. Deep-Dive Engineering Subsystems

### 3.1 Structural Layout Fingerprinting (`src/parser_app/fingerprinter.py`)
To recognize whether a statement layout has been seen before—even when client names, dates, and portfolio values change every month—`LayoutFingerprinter.observe()` performs a two-stage normalization:
* **Dynamic Token Masking:** Strips out currency amounts, dates, account identifiers, and floating-point numbers while preserving structural keywords, section headers, and table column labels.
* **Geometric Quantization:** Combines the normalized structural skeleton into a deterministic `SHA-256` hash (`layout_fingerprint`). If a provider modifies their template (Layout Drift), the hash changes automatically, triggering self-healing recovery learning.

### 3.2 Active-Active Multi-Provider LLM Router (`src/parser_app/orchestrator.py`)
Single-provider AI pipelines are vulnerable to `429 Too Many Requests` rate limits, `503 Service Unavailable` outages, and model-specific coordinate hallucinations.
* The `LearningOrchestrator` accepts an ordered routing pool of `LLMClient` implementations (`[GroqLLMClient, GeminiLLMClient]`).
* Each client uses `tenacity` exponential backoff (`wait_exponential(multiplier=2, min=2, max=10)`), strips markdown wrappers via `clean_llm_json()`, and validates the response against the strict Pydantic `LayoutArtifact` schema.
* **Closed-Loop Verification:** If Provider 1 (`Groq`) returns syntactically valid JSON whose coordinates fail mathematical reconciliation on the document, the orchestrator automatically logs a warning, marks the candidate `REJECTED`, and fails over to Provider 2 (`Gemini`) within the same transaction.

### 3.3 Deterministic Geometric Parser (`src/parser_app/parser_engine.py`)
Once a `LayoutArtifact` is loaded, `DeterministicParser` extracts data without regex fragility using four specialized mechanisms:

| Mechanism | Engineering Problem Solved | Implementation Detail |
| :--- | :--- | :--- |
| **Proximity Summary Scanner** | Dense statements place multiple summary metrics on the exact same horizontal Y-axis (e.g., `Cash Balance: 1500000.00` at `X:40, Y:680` and `Accrued Interest: 25000.00` at `X:350, Y:680`). Naive line scanners grab the wrong number. | Matches the target label (`Cash`), slices the line string at `line[match.end():]`, and extracts the **first** valid numeric token immediately following the label, supplemented by full-text regex fallbacks. |
| **Center-of-Mass Column Projection** | Long numbers (e.g., `10000000.00`) frequently overflow tight bounding boxes by 2–5 pixels, causing strict `x0 >= start and x1 <= end` checks to drop cells. | Computes each word's horizontal center of mass $\text{mid}_x = \frac{x_0 + x_1}{2}$ and projects it against column spans with adaptive padding (`-15.0pt` left, `+35.0pt` right on the rightmost valuation column). |
| **Multi-Page Finite State Machine (FSM)** | Multi-page tables are interrupted by bottom-of-page disclaimers (`Page 1 of 4`), repeated page-top banners (`PORTFOLIO HOLDINGS (CONTINUED PAGE 2)`), and trailing sections (`TRANSACTION LEDGER`). | Tracks state (`SEARCHING` $\rightarrow$ `ACTIVE_TABLE` $\rightarrow$ `TERMINATED`). Suppresses repeated headers and `CONTINUED` banners **before** evaluating running footers (`\bpage\s+\d+\s+of\s+\d+\b`), allowing seamless extraction across arbitrary page counts until a true terminal section is reached. |
| **Fuzzy Column Synonym Resolution** | Different LLMs may name columns `security_name`, `Security Description`, `Scrip`, or `market_value`, `Market Value`, `Amount`. | Normalizes column keys via synonym lookup buckets with positional fallback (leftmost column $\rightarrow$ security name; rightmost column $\rightarrow$ market value). |

### 3.4 Financial Validation & Quarantine Engine (`src/parser_app/validator.py`)
All monetary values are represented exclusively using Python's `decimal.Decimal` (never IEEE 754 `float`). The validator enforces:
1. **Non-Empty Holdings Check:** Rejects any parse that yields zero holdings when a positive closing value is stated.
2. **Portfolio Reconciliation Identity:**
   $$\left\vert{} \left( \sum_{i=1}^{n} \text{Holding}_i.\text{market\_value} + \text{Summary.cash\_balance} \right) - \text{Summary.closing\_value} \right\vert{} \le ₹0.05$$
3. **Quarantine Guarantee:** Any statement failing reconciliation is flagged `ValidationStatus.FAIL` with exact diagnostic discrepancy math (e.g., `Expected 21500000.00, got 56500000.00 (Diff: 35000000.00)`) and held in the quarantine queue for operator review.

### 3.5 Layout Drift Detection & Self-Healing (`src/parser_app/artifact_repository.py`)
When a known wealth manager (e.g., `AlphaWealth`) redesigns its PDF template, the structural fingerprint changes.
* `_detect_drift_provider()` scans the document text against all known active provider names in `artifacts.db`.
* Upon detecting a known provider with a new fingerprint, the orchestrator logs a **Layout Drift Event**, passes the provider hint to the LLM learning loop, promotes the newly validated artifact to `ACTIVE`, and atomically transitions the old layout artifact to `DEPRECATED`.

---

## 4. Canonical Data Contracts

### 4.1 Learned Layout Artifact Schema (`artifacts.db`)
```json
{
  "artifact_version": "1.0",
  "layout_fingerprint": "2463bf7ae4cd1af6a3b3aa6fd79cb3ad37ad1cfa7ef1f0b2f21c64444502591d",
  "provider_name": "TITAN WEALTH ENTERPRISES",
  "context_rules": [],
  "summary_rules": [
    { "name": "opening_value", "label": "Opening", "direction": "right", "offset_words": 1 },
    { "name": "cash_balance", "label": "Cash", "direction": "right", "offset_words": 1 },
    { "name": "closing_value", "label": "Closing", "direction": "right", "offset_words": 1 }
  ],
  "holdings_table": {
    "start_anchor": "PORTFOLIO HOLDINGS",
    "columns": [
      { "name": "security_name", "x_start": 50.0, "x_end": 195.0 },
      { "name": "isin", "x_start": 200.0, "x_end": 310.0 },
      { "name": "quantity", "x_start": 320.0, "x_end": 410.0 },
      { "name": "market_value", "x_start": 420.0, "x_end": 520.0 }
    ]
  }
}
```

### 4.2 Extracted Statement Output Schema (`statements.db`)
```json
{
  "statement_id": "STMT-2228d465",
  "context": {
    "provider_name": "TITAN WEALTH ENTERPRISES",
    "strategy_name": "Consolidated Portfolio",
    "client_identifier": "TITAN-8821-X",
    "statement_period": "Oct 2026",
    "currency": "INR"
  },
  "summary": {
    "opening_value": "50000000.00",
    "closing_value": "56500000.00",
    "cash_balance": "1500000.00",
    "fees_charged": null,
    "nav_per_unit": null
  },
  "holdings": [
    {
      "security_name": "Titan Equity Fund 1",
      "isin": "INE000T01001",
      "quantity": "1000",
      "cost": "0",
      "market_value": "5000000.00",
      "weight": null
    }
  ],
  "transactions": [
    {
      "date": "2026-10-12",
      "transaction_type": "buy",
      "security": "Titan Gold ETF",
      "quantity": "5000",
      "amount": "5000000.00"
    }
  ],
  "provenance": {
    "source_hash": "2228d465ec1af8549c1296760b61770f78076e301218ce3d1e28ac18d7c3e1ef",
    "layout_fingerprint": "2463bf7ae4cd1af6a3b3aa6fd79cb3ad37ad1cfa7ef1f0b2f21c64444502591d",
    "artifact_version": "1.0"
  },
  "validation": {
    "status": "PASS",
    "details": "Portfolio sum matched (Diff: 0.00) | No NAV per unit provided."
  }
}
```

---

## 5. Repository Structure

```text
activeMoney/
├── .env.example                     # Template for API keys and Gmail IMAP credentials
├── pyproject.toml                   # Project metadata, pytest & ruff configuration
├── README.md                        # System architecture & operational runbook
├── known_limitations.md             # Concrete failure modes & engineering trade-offs
├── ai_usage_log.md                  # Transparent log of AI assistance & human verification
├── data/
│   ├── artifacts.db                 # SQLite store for learned LayoutArtifacts (ACTIVE/REJECTED)
│   ├── statements.db                # SQLite store for extracted statements & quarantine state
│   └── staging/                     # Content-addressed (SHA-256) PDF staging directory
├── scripts/
│   ├── gmail_collector.py           # Live SSL IMAP daemon for unread statement emails
│   ├── parse.py                     # Master CLI pipeline with multi-provider routing & metrics
│   ├── review.py                    # CLI quarantine manager with automatic PII masking
│   ├── dashboard.py                 # Streamlit Executive Web UI & Portfolio Inspector
│   ├── generate_complex_pdf.py      # 3-page Omega Wealth synthetic generator
│   ├── generate_titan_stress_test.py# 4-page Titan Wealth stress test (10 holdings, footers, txns)
│   └── generate_zephyr_pdf.py       # 1-page Zephyr Quantum hostile layout (Y-axis collisions)
├── src/
│   └── parser_app/
│       ├── __init__.py
│       ├── schema.py                # Canonical Pydantic v2 financial domain models (Decimal)
│       ├── artifact_schema.py       # Declarative JSON ruleset schema for layout artifacts
│       ├── fingerprinter.py         # Structural normalization & SHA-256 layout fingerprinting
│       ├── artifact_repository.py   # SQLite persistence & drift deprecation state machine
│       ├── statement_repository.py  # SQLite persistence for parsed outputs & operator resolution
│       ├── llm_client.py            # Abstract LLMClient protocol, JSON cleaner & MockLLMClient
│       ├── groq_client.py           # Primary high-speed LLM compiler (Groq openai/gpt-oss-20b)
│       ├── gemini_client.py         # Fallback spatial LLM compiler (Google Gemini 3.8 Flash)
│       ├── parser_engine.py         # Center-of-Mass & Multi-Page FSM deterministic extractor
│       ├── validator.py             # Strict Decimal financial reconciliation engine
│       ├── orchestrator.py          # Self-learning loop, drift detector & multi-LLM router
│       ├── ingestor.py              # RFC822 MIME parser, magic-byte & path-traversal guard
│       └── queue_worker.py          # ThreadPoolExecutor batch processor & PipelineMetrics
└── tests/
    ├── fixtures/                    # Synthetic & adversarial PDF/EML test fixtures
    ├── test_schema.py               # Unit tests for Decimal coercion & schema bounds
    ├── test_fingerprinter.py        # Unit tests for structural hash invariance
    ├── test_validator.py            # Unit tests for reconciliation math & edge cases
    ├── test_artifact_repo.py        # Unit tests for artifact promotion & drift deprecation
    ├── test_llm_client.py           # Offline unit tests for LLM timeouts & JSON hallucinations
    ├── test_parser_engine.py        # Unit tests for geometric coordinate extraction
    ├── test_orchestrator.py         # Unit tests proving the 0-LLM-call Golden Rule invariant
    └── test_ingestor.py             # Security tests for spoofing, path traversal & deduplication
```

---

## 6. Installation & Configuration

### 6.1 Prerequisites
* **Python:** `3.10+` (Tested on Python 3.11 / 3.12 on Windows PowerShell & Linux)
* **LLM Credentials:** A [Groq API Key](https://console.groq.com) (Primary) and/or [Google Gemini API Key](https://aistudio.google.com) (Fallback). *Note: All unit tests run 100% offline using `MockLLMClient` without requiring live keys.*
* **Email Credentials (Optional for Live IMAP):** A Gmail test account with 2-Step Verification and a 16-character **Google App Password**.

### 6.2 Step-by-Step Setup
```powershell
# 1. Clone the repository and navigate to root
cd activeMoney

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # On Linux/macOS: source venv/bin/activate

# 3. Install core dependencies and tooling
pip install -e .
pip install groq google-genai pdfplumber pydantic python-dotenv tenacity reportlab streamlit pandas pytest ruff
```

### 6.3 Environment Variables (`.env`)
Create a `.env` file in the root directory (never committed to Git):
```env
# Primary High-Speed Spatial Compiler
GROQ_API_KEY=gsk_your_actual_groq_key_here

# Secondary Fallback Spatial Compiler
GEMINI_API_KEY=AIza_your_actual_gemini_key_here

# Live Gmail IMAP Ingestion Credentials
GMAIL_USER=your_test_inbox@gmail.com
GMAIL_APP_PASSWORD=your16charapppassword
```

---

## 7. Operational Runbook & Verification Walkthrough

### 7.1 Generate Adversarial Stress-Test Statements
Generate synthetic PDFs engineered to test hostile edge cases (Y-axis summary collisions, 6-column tight tables, 4-page table continuations with running footers, and embedded transaction ledgers):
```powershell
python scripts/generate_zephyr_pdf.py
python scripts/generate_titan_stress_test.py
python scripts/generate_complex_pdf.py
```

### 7.2 Live End-to-End Gmail Ingestion (`scripts/gmail_collector.py`)
1. Email `zephyr_hostile_test.pdf` or `titan_stress_test.pdf` as an attachment to your configured `GMAIL_USER` inbox and leave the email **Unread**.
2. Run the IMAP collector:
```powershell
python scripts/gmail_collector.py
```
**How Statement Identification Works:** The collector queries `imap.gmail.com` over SSL (`IMAP4_SSL`) for `UNSEEN` messages, inspects MIME parts for `.pdf` filenames, passes raw RFC822 bytes to `EmailIngestor` (which verifies the `%PDF-` magic header to block spoofed executables), and stages the file under its `SHA-256` content hash in `data/staging/`.

### 7.3 Run the Self-Learning Parser Pipeline (`scripts/parse.py`)
**Run 1 — Cold Start (Learning Mode):**
```powershell
python scripts/parse.py --input data/staging
```
* **What happens:** The orchestrator detects unknown layout fingerprints, invokes the Groq/Gemini routing pool, validates that `AlphaWealth` (`₹1,500,000.00`), `Zephyr Quantum Wealth` (`₹26,500,000.00`), and `Titan Wealth Enterprises` (`₹56,500,000.00` across 4 pages and 10 holdings) reconcile to `Diff: 0.00`, promotes all 3 layout artifacts to `ACTIVE`, and outputs a `100.0%` validation pass rate.

**Run 2 — Warm Cache (Proving the Zero-LLM-Call Golden Rule):**
Immediately re-run the exact same command without clearing `data/artifacts.db`:
```powershell
python scripts/parse.py --input data/staging
```
* **What happens:** All 3 layout fingerprints match `ACTIVE` records in `artifacts.db`. **Zero HTTP requests** are made to Groq or Gemini. Execution time drops from ~45–70 seconds (API bound) to **< 0.40 seconds** (~8+ documents/second local CPU bound).

### 7.4 Launch the Executive Web Dashboard (`scripts/dashboard.py`)
```powershell
streamlit run scripts/dashboard.py
```
Open `http://localhost:8501` in your browser to access:
* **Executive KPI Ribbon:** Live counts of Processed Statements, Verified (`PASS`) Statements, Active Learned Formats (`0-LLM`), and Pending Quarantine items.
* **Pipeline Control Sidebar:** Trigger live Gmail IMAP synchronization, run the parser on `data/staging` or `tests/fixtures/raw_pdfs`, and toggle the **🔒 Mask Client PII (Compliance Mode)** switch.
* **Portfolio & Holdings Explorer:** Inspect statement summaries, reconciliation proofs, interactive holdings tables, and raw JSON payloads with provenance hashes.
* **Human-Attention Quarantine Queue:** Review diagnostic failure reasons for rejected statements and mark items as resolved.
* **Learned Format Artifacts Registry:** Inspect the exact spatial coordinate JSON rulesets stored in `artifacts.db`.

### 7.5 CLI Quarantine & Review Tool (`scripts/review.py`)
For headless server operations or CI pipelines, inspect results directly from the terminal:
```powershell
# List all verified statements
python scripts/review.py list --status PASS

# List all quarantined statements requiring human review
python scripts/review.py list --status FAIL

# Inspect full JSON output with automatic client PII redaction
python scripts/review.py view STMT-2228d465

# Mark a quarantined statement as resolved by an operator
python scripts/review.py resolve QUAR-dc0dce8b
```

### 7.6 Automated Test Suite & Static Analysis
All unit tests are hermetically isolated and run offline without API keys or network access:
```powershell
# Run the complete pytest suite
pytest -v

# Run Ruff linter and formatter checks
ruff check .
```

---

## 8. Stress-Test Benchmark Matrix

| Test Fixture | Provider / Archetype | Pages | Structural Traps Tested | Reconciliation Math | Result |
| :--- | :--- | :---: | :--- | :--- | :---: |
| `alpha_wealth.pdf` | **AlphaWealth PMS** | 1 | Standard baseline layout, multi-row equity table | `₹1,250,000` Holdings + `₹250,000` Cash = `₹1,500,000` Closing | ✅ **PASS** |
| `zephyr_hostile_test.pdf` | **Zephyr Quantum Wealth** | 1 | Verbose labels, Y-axis collision (`Cash` vs `Accrued Interest` at `Y:680`), 6 tight columns, dense legal footer | `₹25,000,000` Holdings + `₹1,500,000` Cash = `₹26,500,000` Closing | ✅ **PASS** |
| `titan_stress_test.pdf` | **Titan Wealth Enterprises** | 4 | Distraction fee schedule on P1, 10 holdings split across P1–P3, running footers (`Page X of 4`) on every page, repeated `CONTINUED` headers, Transaction Ledger on P3 | `₹55,000,000` Holdings (P1: `20M`, P2: `30M`, P3: `5M`) + `₹1,500,000` Cash = `₹56,500,000` Closing | ✅ **PASS** |
| `beta_aif.pdf` | **Beta Capital AIF** | 1 | Non-PMS commitment/drawdown semantics (No standard holdings table) | Safely rejected by `FinancialValidator` (`No holdings to verify sum`) | 🛡️ **QUARANTINED** |
| `gamma_wealth.pdf` | **Gamma Wealth** | 1 | Corrupt/unverifiable summary structure | Safely rejected by `FinancialValidator` | 🛡️ **QUARANTINED** |

---

## 9. Security, Privacy & Compliance Posture

* **Zero Production LLM Data Exposure:** Client statements matching known templates are parsed 100% locally via `pdfplumber` and Python `Decimal` math; no client data leaves the host machine.
* **PII Redaction by Default:** Both `scripts/review.py` and `scripts/dashboard.py` mask `client_identifier` fields (`*** REDACTED PII ***`) by default to prevent accidental screen-sharing or log leakage.
* **MIME & Binary Hardening:** `EmailIngestor` validates `%PDF-` magic headers on all email attachments and strips directory paths via ` os.path.basename()` + regex sanitization before writing to disk.
* **Secret Hygiene:** All API keys and IMAP credentials are loaded strictly via environment variables (`.env`), with zero hardcoded credentials in source history.
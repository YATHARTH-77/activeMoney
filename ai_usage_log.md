# 🧠 AI Usage Log & Human-AI Engineering Audit

> **Purpose of This Document:** This log provides an transparent, auditable record of how Artificial Intelligence was used both **at development time** (as an interactive pair-programming and architectural sounding board) and **at runtime** (as a strictly bounded spatial layout compiler inside the application). Most importantly, it documents the exact technical failures where AI-generated code or LLM runtime outputs broke under adversarial stress testing, and the human-driven engineering interventions that resolved them.

---

## 1. Executive Summary: Division of Responsibility

| Engineering Dimension | Role of AI Assistant (Development Time) | Role of Human Engineer (Ownership & Control) |
| :--- | :--- | :--- |
| **Core Architecture** | Proposed initial module scaffolding and Pydantic/SQLite boilerplate patterns. | Enforced **"The Golden Rule"** (0 LLM calls for known layouts), strict `Decimal` math, and total separation between LLM rule synthesis and deterministic extraction. |
| **Adversarial Stress Testing** | Generated baseline `ReportLab` PDF scripts (`alpha_wealth.pdf`). | Demanded hostile 1-page (`Zephyr`) and 4-page (`Titan`) stress tests with Y-axis collisions, tight 6-column layouts, running footers, and page-break traps to break the parser. |
| **Failure Diagnosis & Debugging** | Assisted with stack-trace inspection and regex refactoring. | Identified silent partial-extraction bugs, rejected brittle word-offset heuristics, and mandated upgrades to **Center-of-Mass Projection** and a **Multi-Page Finite State Machine**. |
| **Infrastructure & Resilience** | Drafted initial single-provider `GeminiLLMClient`. | Identified quota exhaustion risks on Gemini, initiated the pivot to **Groq**, diagnosed model deprecation (`404`) and concurrency (`429`) issues, and architected the **Multi-Provider Fallback Router**. |
| **Production Operations** | Generated CLI review scripts (`review.py`). | Directed the end-to-end live **Gmail IMAP SSL integration** (`gmail_collector.py`) and the **Streamlit Executive Web UI** (`dashboard.py`) with PII compliance masking. |

---

## 2. Development-Time AI vs. Runtime AI Separation

### 2.1 Development-Time AI Tooling
* **Tool Used:** Google Gemini (Interactive Pair-Programming & Architecture Collaboration)
* **Scope of Use:**
  1. Accelerating boilerplate generation for Pydantic v2 models (`src/parser_app/schema.py`, `src/parser_app/artifact_schema.py`).
  2. Writing SQLite repository persistence methods (`ArtifactRepository`, `StatementRepository`).
  3. Generating synthetic and adversarial PDF test fixtures using `reportlab` (`generate_zephyr_pdf.py`, `generate_titan_stress_test.py`).
  4. Scaffolding the Streamlit operational dashboard (`scripts/dashboard.py`) and CLI runners (`scripts/parse.py`, `scripts/review.py`).

### 2.2 Runtime AI Tooling (Inside the Pipeline)
* **Models Used:**
  * **Primary Spatial Compiler:** Groq API (`openai/gpt-oss-20b`) via `src/parser_app/groq_client.py`
  * **Fallback Spatial Compiler:** Google GenAI SDK (`gemini-3.8-flash`) via `src/parser_app/gemini_client.py`
  * **Offline Test Double:** `MockLLMClient` via `src/parser_app/llm_client.py` (guarantees 100% offline unit test execution with zero API keys).
* **Strict Architectural Boundary:** Runtime LLMs **never** extract financial figures into the database. They receive a spatial coordinate sample of an unseen PDF and output a JSON `LayoutArtifact` (column X-boundaries and summary anchor labels). If the resulting deterministic parse fails `FinancialValidator` reconciliation ($\sum \text{Holdings} + \text{Cash} == \text{Closing}$), the LLM's output is rejected.

---

## 3. Forensic Log of AI Failures & Engineering Corrections

The highest-value engineering work in this project occurred when initial AI-generated designs failed against real-world PDF complexities. Below are the **7 critical failure modes** encountered during development and how we re-engineered the system to solve them.

---

### Failure Case 01: Brittle Word-Offset Counting & Sub-Pixel Column Clipping
* **Test Case:** `zephyr_hostile_test.pdf` (Hash: `0fe904ef...` — 6 tightly packed columns, verbose summary labels).
* **What the AI Initially Generated:**
  1. For summaries, the initial prompt asked the LLM to count `offset_words` between a label and its number (e.g., `"Total Settled Cash Balance (INR): 1500000.00"` $\rightarrow$ `offset_words = 4`).
  2. For tables, the parser required words to fit strictly inside LLM-estimated column boxes: `col.x_start <= w["x0"] and w["x1"] <= col.x_end`.
* **How It Broke in Testing:**
  ```text
  WARNING: Candidate rejected due to financial mismatch: No holdings to verify sum. | No NAV per unit provided.
  ```
  * The LLM miscounted word offsets by 1 token, extracting `"(INR):"` instead of `"1500000.00"`, which defaulted to `0`.
  * In the dense 6-column table (`Avg Cost` at `X:360`, `Market Value` at `X:430`), large numbers like `10000000.00` stretched 3 pixels past `col.x_end`, causing the strict bounding-box check to drop every single row (`0` holdings extracted).
* **Engineering Fix Implemented:**
  * **Eliminated Word-Offset Counting:** Replaced `offset_words` arithmetic with a horizontal regex numeric scanner.
  * **Center-of-Mass Geometric Projection:** Upgraded `_extract_holdings()` in `src/parser_app/parser_engine.py` to compute each word's horizontal midpoint ($\text{mid}_x = \frac{x_0 + x_1}{2}$) with adaptive tolerance (`-15.0pt` left, `+35.0pt` right for the rightmost valuation column).

---

### Failure Case 02: The Horizontal Y-Axis Summary Collision (`Diff: 1,475,000.00`)
* **Test Case:** `zephyr_hostile_test.pdf` (Run 2 after enabling Center-of-Mass projection).
* **What Happened:** The holdings table extracted all 3 ETFs (`₹25,000,000.00`), yet validation failed with a bizarre discrepancy:
  ```text
  WARNING: Candidate rejected due to financial mismatch: Portfolio sum mismatch. Expected 25025000.00, got 26500000.00 (Diff: 1475000.00)
  ```
* **Root Cause Diagnosis:**
  In `generate_zephyr_pdf.py`, two independent metrics were placed at the exact same vertical coordinate (`Y = 680`):
  ```python
  c.drawString(40, 680, "Total Settled Cash Balance (INR): 1500000.00")
  c.drawString(350, 680, "Accrued Interest (Not Settled): 25000.00")
  ```
  `pdfplumber` merged both into a single horizontal text line:
  `"Total Settled Cash Balance (INR): 1500000.00 Accrued Interest (Not Settled): 25000.00"`
  The AI-suggested summary scanner used `numbers[-1]` (grabbing the *last* number on the matched line), which extracted `25,000.00` (Accrued Interest) instead of `1,500,000.00` (Cash Balance)! Thus: $25,000,000 + 25,000 = 25,025,000 \neq 26,500,000$.
* **Engineering Fix Implemented (Proximity Summary Scanner):**
  Rewrote `_extract_summary()` to locate the exact character index where the matched label ends (`line[match.end():]`) and extract `numbers[0]`—the **first** numeric value immediately following the label:
  ```python
  match = re.search(label_pattern, line, re.IGNORECASE)
  if match:
      text_after_label = line[match.end():]
      numbers = re.findall(r"[-+]?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b", text_after_label)
      if numbers:
          clean_val = numbers[0].replace(",", "")
  ```
  Result: `Zephyr Quantum Wealth` immediately reconciled (`25,000,000 + 1,500,000 == 26,500,000`) and promoted to `ACTIVE`.

---

### Failure Case 03: Multi-Page Substring Collision (`"page "` vs `"CONTINUED PAGE 2"`)
* **Test Case:** `titan_stress_test.pdf` (Hash: `2228d465...` — 4 pages, 10 holdings split across Pages 1–3 totaling `₹55,000,000`, running footers on every page).
* **What Happened:** The parser extracted the 4 holdings on Page 1 (`₹20,000,000`) plus Cash (`₹1,500,000`), but completely skipped Pages 2 and 3:
  ```text
  WARNING: Candidate rejected due to financial mismatch: Portfolio sum mismatch. Expected 21500000.00, got 56500000.00 (Diff: 35000000.00)
  ```
* **Root Cause Diagnosis:**
  1. To handle running footers (`"Disclaimer: ... Page 1 of 4"`), the AI assistant added `"page "` to `page_footer_indicators` and placed the footer check **before** the repeated-header suppression check, executing a `break` out of the page loop whenever `"page "` was seen.
  2. At the very top of Page 2 (`Y = 750`), the continuation header read: `"PORTFOLIO HOLDINGS (CONTINUED PAGE 2)"`.
  3. On the very first line of Page 2, the parser matched `"page "` inside `"PAGE 2"`, assumed it had reached the bottom footer of Page 2, and executed `break`—abandoning all 5 holdings on Page 2 (`₹30M`) and the final holding on Page 3 (`₹5M`)!
* **Engineering Fix Implemented:**
  1. **Reordered State Machine Evaluation:** Placed header and continuation banner suppression (`"continued"`, `"portfolio holdings"`, `"security" + "isin"`) **strictly before** footer filtering.
  2. **Replaced `break` with Line-Level Regex Filtering:** Replaced the naive `"page "` substring check with a word-bounded regex (`r"\bpage\s+\d+\s+of\s+\d+\b"`) that `continue`s past the footer line without aborting the page scan.

---

### Failure Case 04: SQLite `ON CONFLICT DO UPDATE` & `cursor.lastrowid` Bug
* **Where It Occurred:** `src/parser_app/artifact_repository.py` (`ArtifactRepository.save_candidate`)
* **Root Cause Diagnosis:**
  The initial AI-written `save_candidate` method used SQLite's upsert syntax (`INSERT INTO artifacts ... ON CONFLICT(fingerprint) DO UPDATE ...`) and returned `cursor.lastrowid`. In Python's `sqlite3` driver, when an `ON CONFLICT DO UPDATE` clause modifies an *existing* row rather than inserting a new row, `cursor.lastrowid` returns `0` (or the previous insert ID), causing `promote_to_active(cand_id)` to silently fail to update the status from `REJECTED` to `ACTIVE` on subsequent re-learning runs.
* **Engineering Fix Implemented:**
  Replaced `return cursor.lastrowid` with an explicit primary-key lookup inside the transaction:
  ```python
  cursor.execute("SELECT id FROM artifacts WHERE fingerprint = ?", (artifact.layout_fingerprint,))
  return cursor.fetchone()[0]
  ```

---

### Failure Case 05: Schema Contract Desynchronization (`ImportError` & Pydantic `ValidationError`)
* **What Happened:**
  1. During the parser engine upgrade, `from parser_app.artifact_schema import SummaryRule, TableRule` raised an `ImportError` because the earlier `artifact_schema.py` had not exposed those sub-models at the module level.
  2. When Page 3 of `titan_stress_test.pdf` extracted the transaction row (`2026-10-12 buy Titan Gold ETF 5000 5000000.00`), Pydantic raised:
     `1 validation error for Transaction: transaction_type Field required [type=missing]`.
* **Engineering Fix Implemented:**
  1. Explicitly defined and exported `ContextRule`, `SummaryRule`, `ColumnRule`, and `TableRule` in `src/parser_app/artifact_schema.py`.
  2. Aligned `DeterministicParser._extract_transactions()` with `src/parser_app/schema.py` by passing `transaction_type=t_type.lower()`.

---

### Failure Case 06: Groq Model Deprecation (`HTTP 404`) & Free-Tier Rate Thrashing (`HTTP 429`)
* **What Happened:**
  1. When integrating Groq to avoid Gemini quota exhaustion, the initial model identifier `llama-3.3-70b-versatile` returned:
     `Error code: 404 - {'error': {'message': 'The model llama-3.3-70b-versatile does not exist or you do not have access to it.'}}`
  2. After switching to `openai/gpt-oss-20b`, running `StatementProcessor` with `max_workers=4` fired 3 simultaneous multi-page spatial prompts at Groq within 10 milliseconds, triggering continuous `HTTP/1.1 429 Too Many Requests` backoff loops.
  3. On `alpha_wealth.pdf` (`fcc9f761...`), the LLM returned column names like `"Security"` instead of `"security_name"` and copied coordinate brackets (`[P1 | X: ...]`) into `start_anchor`, causing 0 holdings to be extracted.
* **Engineering Fix Implemented:**
  1. **Active-Active Multi-Provider Router (`orchestrator.py`):** Configured `LearningOrchestrator` to iterate through `[GroqLLMClient(model="openai/gpt-oss-20b"), GeminiLLMClient(model="gemini-3.8-flash")]`. If Provider 1 errors or fails math validation, it automatically falls back to Provider 2.
  2. **Line-Grouped Spatial Compression & Anchor Sanitization:** Compressed the LLM prompt from 450 raw word tokens per page to 35 line-grouped rows (`[Y:top] X:x0-x1 'text'`), cutting token consumption by ~65%, and stripped any hallucinated `[...]` brackets from `start_anchor`.
  3. **Fuzzy Column Synonym Resolution:** Added `find_cell()` in `parser_engine.py` to match column name variations (`security`/`scrip`/`name` and `market_value`/`value`/`amount`) with positional fallback.
  4. **Worker Serialization for Rate-Limit Safety:** Set default `max_workers=1` in `scripts/parse.py` and `scripts/dashboard.py` to respect free-tier TPM limits.

---

### Failure Case 07: Streamlit 2026 API Deprecation & UI/CLI Router Desynchronization
* **What Happened:**
  Launching `streamlit run scripts/dashboard.py` produced deprecation warnings:
  `Please replace use_container_width with width. use_container_width will be removed after 2025-12-31. For use_container_width=True, use width='stretch'.`
  Furthermore, triggering the pipeline from the Streamlit sidebar initially used the legacy single-provider Gemini client with `max_workers=4` instead of the new Groq+Gemini router.
* **Engineering Fix Implemented:**
  Synchronized `run_pipeline_from_ui()` in `scripts/dashboard.py` with the exact Multi-Provider `[GroqLLMClient, GeminiLLMClient]` routing pool and `max_workers=1` configuration from `scripts/parse.py`, and migrated all Streamlit button and dataframe layout parameters to `width="stretch"`.

---

## 4. Evolution of the Runtime Spatial Prompt

A core finding of our engineering process is that **how spatial PDF data is formatted for the LLM compiler directly determines extraction accuracy**.

### Iteration 1 (Naive Text Dump — Discarded)
Passing raw `page.extract_text()` without coordinates made it impossible for the LLM to know `x_start` and `x_end` pixel bounds for table columns.

### Iteration 2 (Per-Word Token Stream — High Token Cost & Bracket Hallucinations)
```text
[P1 | X: 40.0 -> 82.3, Y: 595.0] Quantum
[P1 | X: 85.1 -> 110.4, Y: 595.0] Tech
```
* **Problem:** Consumed ~3,500 tokens per document, triggered Groq `429` TPM limits when parallelized, and caused smaller models to copy `[P1 | X: ...]` into the `start_anchor` JSON field.

### Iteration 3 (Final Production Format: Y-Clustered Horizontal Line Map)
In `src/parser_app/orchestrator.py`, words are pre-clustered by vertical `Y` coordinate (`tolerance = 3.5pt`) before building the prompt:
```text
--- PAGE 1 ---
[Y:615] X:40-118 'Security Description' | X:200-241 'ISIN Code' | X:300-334 'Quantity' | X:430-482 'Market Value'
[Y:595] X:40-132 'Quantum Tech ETF Class B' | X:200-258 'INE999Q01011' | X:300-318 '5000' | X:430-476 '10000000.00'
```
* **Why This Succeeded:**
  1. Reduces prompt size by **>60%**, preventing rate-limit exhaustion.
  2. Visually aligns column headers (`[Y:615]`) directly above data cells (`[Y:595]`), allowing both `openai/gpt-oss-20b` and `gemini-3.8-flash` to infer non-overlapping `x_start` and `x_end` bounds on the first attempt.

---

## 5. Verification & Quality Assurance Audit

Every line of AI-assisted code was verified against four independent quality gates before project completion:

1. **Automated Offline Unit Test Suite (`pytest`):**
   * Verified `Decimal` coercion, SHA-256 structural fingerprinting invariance, SQLite artifact state transitions (`CANDIDATE` $\rightarrow$ `ACTIVE` / `REJECTED` / `DEPRECATED`), `MockLLMClient` timeout/malformed-JSON resilience, and `EmailIngestor` security guards (`%PDF-` magic bytes & path traversal).
2. **Adversarial Multi-Archetype Stress Tests:**
   * Verified 100% mathematical pass rate (`3/3 PASS`, `0 Quarantined`) across `AlphaWealth` (1-page baseline), `Zephyr Quantum Wealth` (1-page hostile density & Y-axis collision), and `Titan Wealth Enterprises` (4-page multi-table continuation with running footers and transaction ledger).
3. **The Zero-LLM-Call Warm Cache Invariant:**
   * Confirmed via HTTP request logging that re-running `python scripts/parse.py --input data/staging` against populated `artifacts.db` makes **0 external API calls** to Groq or Gemini and completes in `< 0.40 seconds`.
4. **Static Analysis & Linting (`ruff check .`):**
   * Enforced PEP 8 compliance, unused-import removal, and clean module boundaries across `src/`, `scripts/`, and `tests/`.


   AI chat history - https://share.gemini.google/m4verEfjo2rL
   
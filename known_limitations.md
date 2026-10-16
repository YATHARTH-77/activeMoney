# ⚠️ Known Limitations, Edge Cases & Production Roadmap

> **Architectural Design Philosophy:** In financial data engineering, *silent data corruption is a catastrophic failure, whereas loud quarantine is a safe operational state.* Every limitation documented below is intentionally bounded by our **`FinancialValidator`**, ensuring that when the parser encounters an unsupported edge case, it **never emits corrupt financial numbers**—it deterministically routes the document to the Human-in-the-Loop Quarantine Queue (`ValidationStatus.FAIL`).

---

## 1. Executive Risk & Limitation Matrix

| ID | Limitation Category | Concrete Trigger Condition | Current System Behavior (Fail-Safe) | Severity | Production v2 Remediation |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **LIM-01** | **AIF Capital-Call Accounting** | Category I/II AIF statements reporting Commitments, Drawdowns & NAV Units instead of security holdings (`beta_aif.pdf`). | Rejects candidate (`No holdings to verify sum`) & routes to Quarantine Queue. | Medium | Add polymorphic `AIFReconciliationStrategy` ($\text{Units} \times \text{NAV} == \text{Closing}$). |
| **LIM-02** | **Multi-Line Wrapped Security Names** | Very long security names wrapping across 2+ vertical lines while valuation sits on Line 1. | Captures Line 1 name + exact `market_value` (math passes 100%); drops wrapped text suffix on Line 2. | Low | Implement Y-delta row stitching ($\Delta Y < 10\text{pt}$) when adjacent line lacks numeric columns. |
| **LIM-03** | **Scanned / Image-Only & Encrypted PDFs** | Flat rasterized scans without an embedded PDF text layer, or PAN/DOB password-protected PDFs. | Extracts 0 words $\rightarrow$ fails validation $\rightarrow$ quarantines safely without crashing worker pool. | Medium | Integrate pre-ingestion PDF decryption vault + OCR fallback (AWS Textract / Surya OCR). |
| **LIM-04** | **Complex Accounting Adjustments** | Statements where $\text{Closing Value}$ includes separate `Net Payables`, `Accrued Management Fees`, or `Unsettled Trades` outside Cash/Holdings. | Flags exact discrepancy (`Diff: <Adjustment>`) and quarantines for human verification. | Medium | Expand `Summary` schema & validator identity to include `net_payables_receivables`. |
| **LIM-05** | **Mid-Document Landscape Rotation** | Multi-page PDFs where Page 1 is Portrait (`612x792`) but Page 3 rotates to Landscape (`792x612`), shifting X-coordinates. | Page 3 words miss Portrait X-bounds $\rightarrow$ reconciliation sum fails $\rightarrow$ quarantined. | Low | Normalize word coordinates into relative page-width percentages ($x_{\%} = x_0 / \text{page\_width}$). |
| **LIM-06** | **Prose-Induced Fingerprint Drift** | Provider keeps table geometry identical but adds a new 3-paragraph market commentary on Page 1 each month. | Computes new structural hash $\rightarrow$ triggers 1 extra LLM learning call $\rightarrow$ auto-promotes new hash. | Low | Restrict `LayoutFingerprinter` observation strictly to table header regions and font-size skeletons. |
| **LIM-07** | **Transaction Ledger Layouts** | Multi-line or multi-column transaction tables that do not match the canonical `YYYY-MM-DD Type Security Qty Amount` pattern. | Holdings & Summary still validate and `PASS`; non-matching transaction rows are skipped. | Low | Extend `LayoutArtifact` to include a learned `transactions_table: TableRule` coordinate block. |
| **LIM-08** | **Free-Tier LLM Rate Limiting & SQLite Locking** | Burst cold-start ingestion of >10 unseen formats simultaneously on free-tier Groq/Gemini APIs (`HTTP 429`). | Exponential backoff (`tenacity`) + `max_workers=1` serialization adds ~10–40s latency on cold starts. | Low | Migrate artifact/statement stores to PostgreSQL and use paid-tier enterprise LLM endpoints. |

---

## 2. Deep-Dive Technical Analysis of Limitations

### LIM-01: PMS Holdings Reconciliation vs. AIF Drawdown Accounting
* **Where it occurs:** `src/parser_app/validator.py` (`FinancialValidator.validate`)
* **Root Cause:** The validator currently enforces the canonical Portfolio Management Services (PMS) accounting identity:
  $$\sum_{i=1}^{n} \text{Holding}_i.\text{market\_value} + \text{Summary.cash\_balance} = \text{Summary.closing\_value}$$
  However, Category I and Category II Alternative Investment Funds (AIFs)—demonstrated by our `tests/fixtures/raw_pdfs/beta_aif.pdf` fixture—often do not disclose underlying portfolio companies on client statements. Instead, they report **Capital Committed**, **Capital Drawn Down**, **Distributions (DPI)**, and **Units Held $\times$ NAV per Unit = Residual Value**.
* **Why we made this trade-off:** Enforcing a strict, uncompromising mathematical gate for PMS holdings prevented LLM hallucinations across dense equity/debt tables (`AlphaWealth`, `Zephyr`, `Titan`). Relaxing the validator to allow zero-holding statements to pass without an equally strict AIF equation would violate our zero-silent-failure guarantee.
* **Current Fail-Safe Behavior:** `beta_aif.pdf` is deterministically caught with `ValidationStatus.FAIL` (`No holdings to verify sum`) and surfaced in the Quarantine UI/CLI for human inspection.
* **Production v2 Remediation:** Introduce a `statement_archetype: Literal["PMS_HOLDINGS", "AIF_NAV_UNITS", "AIF_CAPITAL_ACCOUNT"]` field in `LayoutArtifact` and route validation through a Strategy Pattern:
  * **PMS Strategy:** $\sum \text{Holdings} + \text{Cash} == \text{Closing}$
  * **AIF NAV Strategy:** $\text{Total Units} \times \text{NAV per Unit} == \text{Closing}$
  * **AIF Capital Account Strategy:** $\text{Opening Capital} + \text{Drawdowns} - \text{Distributions} + \text{Unrealized Gain} == \text{Closing Capital}$

---

### LIM-02: Horizontal Row Grouping & Multi-Line Wrapped Security Names
* **Where it occurs:** `src/parser_app/parser_engine.py` (`DeterministicParser._extract_holdings`)
* **Root Cause:** `pdfplumber` extracts individual word bounding boxes. Our engine reconstructs horizontal table rows by clustering words whose vertical `top` coordinates fall within a `3.5pt` tolerance:
  ```python
  if abs(w["top"] - top) < 3.5:
      matched_top = top
  ```
  In statements where a lengthy security description wraps onto a second physical line:
  ```text
  Y=595.0:  Kotak Emerging Equity Scheme - Direct     INE999Q01011    5000    10000000.00
  Y=604.0:  Plan Growth Option (Lock-in Class B)
  ```
  The engine processes `Y=595.0` as a complete row (since it has a valid `security_name` and `market_value > 0`) and discards `Y=604.0` because its `market_value` cell is empty.
* **Impact:** Financial reconciliation (`market_value`, `quantity`, `cost`, `isin`) remains **100% accurate**, and the statement passes validation. However, `Holding.security_name` only retains the first line (`"Kotak Emerging Equity Scheme - Direct"`), truncating the wrapped suffix.
* **Production v2 Remediation:** Add a **Lookbehind Row-Stitching Pass** in `_extract_holdings`: if a line inside `ACTIVE_TABLE` has text strictly within the `security_name` X-bounds (`c_start <= mid_x <= c_end`), has empty numeric columns, and sits within $\Delta Y \le 12.0\text{pt}$ below the previously extracted `Holding`, append its text to `holdings[-1].security_name`.

---

### LIM-03: Scanned (Raster Image) PDFs & Password-Protected Statements
* **Where it occurs:** `src/parser_app/queue_worker.py` (`StatementProcessor._process_single`)
* **Root Cause:**
  1. **Raster Scans:** Legacy wealth managers occasionally email scanned physical statements (TIFF/JPEG wrapped in a PDF container) with no underlying PostScript text tokens. `page.extract_words()` returns `[]`.
  2. **PDF Encryption:** Indian PMS/AIF providers frequently encrypt statement PDFs using a deterministic client secret (e.g., First 4 letters of Name + DDMM of Birth, or uppercase PAN number).
* **Current Fail-Safe Behavior:**
  * For scanned PDFs, `DeterministicParser` extracts `0` holdings and `0` closing balance, which `FinancialValidator` flags and sends to Quarantine.
  * For encrypted PDFs, `pdfplumber.open()` raises a `PDFPasswordIncorrect` exception caught by `StatementProcessor.process_batch()`, logging a `FATAL Pipeline Error` without crashing the batch worker thread.
* **Production v2 Remediation:**
  1. Maintain a secure **Client Credential Vault** (KMS-backed) mapping `client_email / provider` to candidate decryption keys (PAN, DOB combinations) and decrypt via `pypdf`/`qpdf` in `EmailIngestor` prior to staging.
  2. In `_process_single()`, if `len(words) < 10` on Page 1, route the PDF through an OCR layout engine (**Surya OCR** or **AWS Textract**) to synthesize word bounding boxes `[x0, top, x1, bottom, text]` before passing to `LearningOrchestrator`.

---

### LIM-04: Unmodeled Balance Sheet Adjustments (Payables, Receivables & Margin)
* **Where it occurs:** `src/parser_app/validator.py` & `src/parser_app/schema.py`
* **Root Cause:** Institutional PMS statements occasionally separate accrued expenses or unsettled trades from the Cash Balance:
  $$\text{Net Portfolio Value} = \sum \text{Holdings} + \text{Cash Balance} + \text{Dividends Receivable} - \text{Management Fees Payable}$$
  Because our current schema models `opening_value`, `closing_value`, `cash_balance`, and `fees_charged` (as an informational metric rather than a balance-sheet deduction), a statement with `₹45,000` in unpaid accrued management fees deducted from the closing balance will show a `₹45,000` difference between `Holdings + Cash` and `Closing Value`.
* **Current Fail-Safe Behavior:** Any discrepancy $> ₹0.05$ triggers `ValidationStatus.FAIL` with the exact delta (`Portfolio sum mismatch. Expected X, got Y (Diff: 45000.00)`), allowing an operations analyst to see immediately in the Streamlit dashboard that the difference equals the accrued fee.
* **Production v2 Remediation:** Add `net_adjustments: Optional[Decimal]` (covering receivables, payables, and unsettled trades) to `Summary`, and permit the validator to test a secondary reconciliation identity:
  $$\left\vert{} (\text{Holdings} + \text{Cash} + \text{Net Adjustments}) - \text{Closing Value} \right\vert{} \le ₹0.05$$

---

### LIM-05: Multi-Column Newspaper Layouts & Page Orientation Shifts
* **Where it occurs:** `src/parser_app/parser_engine.py` (Center-of-Mass X-Projection)
* **Root Cause:** `ColumnRule` stores absolute point coordinates (`x_start`, `x_end`) learned from the spatial sample.
  * If a statement prints Page 1 in Portrait (`width = 612pt`) and rotates Page 2 to Landscape (`width = 792pt`) to fit a wide 12-column table, the absolute X-coordinates shift rightward on Page 2.
  * Similarly, if a summary page uses a two-column "newspaper" grid for holdings (two side-by-side holdings tables at `X:40–280` and `X:320–560`), a single set of `ColumnRule` bounds will only capture the left side.
* **Current Fail-Safe Behavior:** Missing the right-hand table or the landscape page causes the extracted holdings sum to fall short of the stated `closing_value`, guaranteeing immediate quarantine.
* **Production v2 Remediation:** Store normalized fractional coordinates ($x_{\text{norm}} \in [0.0, 1.0]$ relative to `page.width`) inside `ColumnRule`, and detect page orientation changes per page (`page.width > page.height`).

---

### LIM-06: Structural Fingerprinting Sensitivity to Unstructured Cover Letters
* **Where it occurs:** `src/parser_app/fingerprinter.py` (`LayoutFingerprinter.observe`)
* **Root Cause:** `LayoutFingerprinter` replaces dates, numbers, and account codes with placeholders (`<NUM>`, `<DATE>`) before hashing the document's text skeleton. While this works across monthly statements that share a static template, some wealth managers prepend a custom 200-word "Fund Manager's Monthly Commentary" on Page 1. Because the prose words change every month, the SHA-256 fingerprint changes even though the underlying Holdings Table coordinates have not moved.
* **Impact:** **Zero impact on accuracy**, because the orchestrator treats the new prose as "Layout Drift", runs a 1-time LLM learning pass, validates the math, and promotes the new artifact. However, it consumes 1 unnecessary LLM API call per monthly commentary change.
* **Production v2 Remediation:** Upgrade `LayoutFingerprinter` to generate a **Geometric Header Hash**: hash only lines that contain high-density tabular alignment (3+ horizontally separated text clusters on the same Y-axis) plus bold section headers, ignoring free-form prose paragraphs ($>15$ words in a single X-span).

---

### LIM-07: Rigid Regex Pattern for Transaction Ledgers
* **Where it occurs:** `src/parser_app/parser_engine.py` (`DeterministicParser._extract_transactions`)
* **Root Cause:** While Holdings and Summaries use LLM-learned geometric rules (`TableRule` and `SummaryRule`), the optional Transaction Ledger extraction currently uses a deterministic regex scanner:
  ```python
  txn_pattern = re.compile(
      r"^(\d{4}-\d{2}-\d{2})\s+(buy|sell|dividend|fee|inflow|outflow)\s+([A-Za-z0-9_\s-]+?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:,\d{3})*(?:\.\d+)?)$",
      re.IGNORECASE,
  )
  ```
  If a provider formats dates as `12-Oct-2026`, uses transaction types like `PURCHASE / REDEMPTION`, or orders columns as `Security | Date | Amount | Qty`, `_extract_transactions` will return an empty list `[]`.
* **Impact:** Holdings and Summary validation still succeed (`PASS`), as transaction reconciliation is not required when holdings sum matches closing value, but transaction rows will be omitted from the JSON output.
* **Production v2 Remediation:** Mirror the `holdings_table: Optional[TableRule]` design by adding `transactions_table: Optional[TableRule]` to `LayoutArtifact`, allowing the Center-of-Mass geometric engine to extract transactions using learned X-coordinates.

---

### LIM-08: IMAP Statefulness & Local SQLite Concurrency
* **Where it occurs:** `scripts/gmail_collector.py` & `src/parser_app/artifact_repository.py`
* **Root Cause:**
  1. **IMAP `UNSEEN` Flag:** Calling `mail.fetch(e_id, "(RFC822)")` in standard IMAP automatically marks the email as `SEEN` (Read) on the Gmail server. If the host machine loses power after downloading to `data/staging/` but before `parse.py` runs, the file remains safely in `data/staging/`, but re-running `gmail_collector.py` will not re-download it unless marked unread.
  2. **SQLite File Locking & Free-Tier API Quotas:** SQLite serializes concurrent `INSERT/UPDATE` writes at the database file level, and free-tier Groq/Gemini endpoints enforce strict requests-per-minute (RPM) and tokens-per-minute (TPM) limits (`HTTP 429`). To guarantee 100% reliability on developer API keys, `max_workers` is defaulted to `1` during cold-start learning.
* **Production v2 Remediation:**
  1. Open the IMAP mailbox in read-only mode (`mail.select("inbox", readonly=True)`) during fetch, and explicitly set the `\Seen` flag (`mail.store(e_id, '+FLAGS', '\\Seen')`) **only after** `EmailIngestor` confirms the SHA-256 file is fsynced to disk and registered in a PostgreSQL ingestion ledger.
  2. Replace SQLite with **PostgreSQL** (`SELECT ... FOR UPDATE SKIP LOCKED`) and deploy behind a Celery / Redis worker pool with enterprise tier LLM rate limits.

---

## 3. Summary: Why This Architecture Is Safe for Production Deployment

Despite the edge cases inherent to unstructured financial PDFs, this system guarantees **Operational Safety** through three architectural invariants:

1. **No Hallucinated Numbers Can Enter the Database:** An LLM never outputs a financial value. It only outputs X/Y coordinate boundaries and text anchors. Every digit in `statements.db` comes directly from the PDF's native character stream via `pdfplumber`.
2. **No Partial Table Extraction Can Pass Silently:** If a multi-page table breaks on Page 3, or if a column boundary clips a number, the sum of extracted holdings will not equal `Closing Value - Cash Balance`. The `FinancialValidator` immediately catches the discrepancy to `₹0.05` precision and blocks promotion.
3. **Full Auditability & Provenance:** Every parsed record permanently links its `source_hash` (SHA-256 of the raw PDF bytes), `layout_fingerprint`, and `artifact_version`, allowing instant replayability when parser logic is upgraded.
# Activv Money: Self-Learning Statement Parser

An elite, deterministic parsing pipeline for Wealth Management PMS and AIF statements. Built to extract financial data with 100% accuracy, this system leverages Generative AI strictly for layout observation while relying entirely on deterministic, mathematically validated geometry for steady-state data extraction.

## 🧠 Architectural Philosophy (The "Golden Rule")

Activv Money's core constraint: *"Use an LLM only once per layout. Subsequent statements of the same layout must be parsed deterministically without AI calls."*

This system achieves this through a strict separation of concerns:
1. **The Brain (LLM):** Used *only* when a brand new, unknown PDF layout is detected. It generates a geometric JSON artifact (ruleset).
2. **The Brawn (Deterministic Parser):** Maps PDF `x_coordinate` bands to extract data natively without AI hallucination. 
3. **The Shield (Financial Validator):** An immutable math engine that verifies `Sum(Holdings) + Cash == Closing Value`.

**If the math fails, the AI's artifact is rejected.** The system never suffers from "silent errors"—it explicitly knows when its own output is wrong.

## 🏗️ System Flow & Lifecycle

1. **Ingestion & Provenance:** Raw emails/PDFs are ingested, checked for MIME types, and cryptographically hashed (`SHA-256`) to ensure idempotency.
2. **Layout Fingerprinting:** Volatile client data (numbers, dates, IDs) is aggressively stripped from the PDF text. The remaining structural boilerplate is hashed to create a stable Layout Fingerprint.
3. **Orchestration & State Management (SQLite):**
   - If the Fingerprint is `ACTIVE` in the DB: The document skips the AI entirely and is parsed deterministically in milliseconds.
   - If the Fingerprint is `UNKNOWN`: The AI is invoked to generate a `CANDIDATE` artifact.
4. **Hypothesis Testing:** The `CANDIDATE` artifact is tested against the raw PDF. If the extracted numbers pass the Financial Math Validator, the artifact is atomically promoted to `ACTIVE`. If it fails, the document is quarantined.

## 🚀 How to Run the Pipeline

### Prerequisites
- Python 3.11+
- `pip install -e .` (Installs dependencies: `pydantic`, `pdfplumber`, `google-genai`, `python-dotenv`)

### Execution (CLI)

**Option 1: Offline / Mock Mode (Recommended for testing without API keys)**
```bash
python scripts/parse.py --mock
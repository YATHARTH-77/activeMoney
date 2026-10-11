# System Architecture

## Component Breakdown
1.  **Collector / Mailbox Transport:** Connects to Gmail, identifies statement emails, and extracts attachments.
2.  **Durable Job Database:** An SQLite database acting as a state machine. It stores raw attachments and tracks their processing state (`READY`, `PROCESSING`, `SUCCEEDED`, `QUARANTINED`).
3.  **Extraction Engine:** Uses `pdfplumber` to read raw text and exact (x,y) bounding box coordinates from pages.
4.  **Fingerprinter:** Strips volatile data (dates, amounts) from the extracted text and creates a structural hash of the page layout (headers, tables, columns).
5.  **LLM Learner:** Interacts with the chosen LLM API. It provides a strict prompt and layout evidence, requesting a JSON parsing configuration in return.
6.  **Deterministic Parser:** The core engine. It reads the JSON artifact (rules) and applies them to the raw coordinate data to extract normalized fields.
7.  **Validation Engine:** Runs accounting and structural checks on the parsed data.
8.  **Review CLI:** The user interface for interacting with the database to check statuses.

## State Machine
*   `CANDIDATE`: A new layout artifact proposed by the LLM, pending validation.
*   `ACTIVE`: An approved layout artifact used by the deterministic parser.
*   `QUARANTINED`: A document that failed deterministic parsing or financial validation, requiring human review.
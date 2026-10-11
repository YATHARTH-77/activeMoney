# System Assumptions & Constraints

## Domain Assumptions
1.  **Accounting Reality:** Not all statements follow standard accounting equations. We assume validation formulas (like Cash Flow reconciliation) are only applied when the statement type explicitly supports them. We will not "fudge" numbers to force equations to balance.
2.  **Passwords:** We assume password-protected PDFs are a known failure state unless a predefined password dictionary/source is provided by the user. The system will quarantine protected PDFs, not attempt to crack them.
3.  **Currency:** All financial values will be cast to `Decimal` types to avoid floating-point precision errors.

## Technical Assumptions
1.  **Concurrency:** A single mailbox may receive multiple statements at the exact same time. The database (SQLite for MVP, structured for Postgres migration) will act as the source of truth for job locking to prevent duplicate LLM calls for the same new layout.
2.  **LLM Reliability:** We assume the LLM will hallucinate. Therefore, the LLM is restricted to generating JSON configuration, which is then strictly validated against a Pydantic schema before being saved as an "Active" artifact.
3.  **Data Privacy:** No real client data will ever be committed to the repository, used in tests, or sent to the LLM without anonymization.
# Requirements Specification
**Project:** Self-Learning PMS/AIF Statement Parser
**Target Date:** October 17, 2026

## 1. Core Objective
Build a pipeline that ingests PMS/AIF statements via email, extracts data into a standard structured schema, and mathematically validates the output. 

## 2. The Golden Invariant (Non-Negotiable)
*   The system may only use an LLM **the first time** it encounters a new statement layout.
*   The LLM must generate a reusable JSON artifact (parsing rules), not extract the data itself.
*   Every subsequent statement matching a known layout must be parsed **deterministically** with exactly zero LLM calls.

## 3. Minimum Viable Product (MVP) Features
1.  **Ingestion:** Connect to Gmail (IMAP/OAuth) to fetch emails and extract PDF attachments.
2.  **Fingerprinting:** Calculate a stable structural hash of a PDF's layout to determine if it is known or unknown.
3.  **Self-Learning (Unknowns):** Send unrecognized layouts to an LLM to generate a constrained JSON parsing configuration.
4.  **Deterministic Extraction (Knowns):** Use the stored JSON config to extract data using exact coordinate mapping and regex, without AI.
5.  **Validation:** Mathematically verify output (e.g., Cash + Holdings Market Value = Closing Value).
6.  **Standard Schema:** Output data strictly to the Activv Money schema (Statement, Holdings, Transactions, Summary).
7.  **Visibility:** A CLI tool to view processed statements, failures, and quarantine queues.

## 4. Stretch Goals (Targeted)
1.  **Layout Drift Detection:** Programmatically detect when a known provider changes their PDF layout (causing validation failures) and trigger a re-learning phase safely.
2.  **Concurrency:** Handle multiple workers processing emails simultaneously without race conditions.
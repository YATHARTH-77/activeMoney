# Activv Money: Self-Learning Statement Parser

A robust, self-learning pipeline that extracts and mathematically validates structured financial data from arbitrary PMS/AIF statement layouts.

## Architecture & Constraints
This system adheres to a strict non-negotiable invariant: **The runtime LLM is only called the very first time an unknown statement format is encountered.** The LLM generates a constrained parsing artifact. All subsequent statements matching that layout are parsed deterministically, offline, with zero AI involvement.

## Setup Instructions
1. Ensure Python 3.11+ is installed.
2. Create and activate a virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -e .` (Once application package is configured)
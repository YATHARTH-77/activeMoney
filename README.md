# Activv Money: Self-Learning PMS/AIF Statement Parser

An enterprise-grade, self-healing document extraction pipeline built for Activv Money. 

This system watches a local directory for incoming PMS/AIF statements, parses them using strict geometric coordinates, and mathematically validates the extraction. It strictly adheres to the Golden Rule: **The LLM is only called once for genuinely unknown formats. Known formats are parsed deterministically with zero LLM calls.**

## 🚀 Quick Start (Local Demo)

1. **Clone & Setup:**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   pip install -r requirements.txt
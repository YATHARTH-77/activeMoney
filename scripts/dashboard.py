import hashlib
import json
import os
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
sys.path.insert(0, src_dir)
sys.path.insert(0, current_dir)

from gmail_collector import collect_unread_emails  # noqa: E402

from parser_app.artifact_repository import ArtifactRepository  # noqa: E402
from parser_app.gemini_client import GeminiLLMClient  # noqa: E402
from parser_app.llm_client import MockLLMClient  # noqa: E402
from parser_app.orchestrator import LearningOrchestrator  # noqa: E402
from parser_app.queue_worker import StatementProcessor  # noqa: E402
from parser_app.statement_repository import StatementRepository  # noqa: E402

load_dotenv()

st.set_page_config(
    page_title="Activv Money | Statement Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for Institutional Fintech Look
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .status-pass {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .status-fail {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_inr(val_str: str) -> str:
    try:
        val = Decimal(str(val_str))
        return f"₹{val:,.2f}"
    except Exception:
        return f"₹{val_str}"


def load_all_artifacts(db_path: str = "data/artifacts.db"):
    if not os.path.exists(db_path):
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, fingerprint, provider_name, status, json_payload, created_at "
            "FROM artifacts ORDER BY created_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]


def run_pipeline_from_ui(input_folder: str, use_mock: bool = False):
    repo = ArtifactRepository(db_path="data/artifacts.db")
    stmt_repo = StatementRepository(db_path="data/statements.db")

    api_key = os.getenv("GEMINI_API_KEY")
    if use_mock or not api_key or api_key == "your_real_api_key_here":
        dummy_json = (
            '{"artifact_version": "1.0", "layout_fingerprint": "mock", '
            '"provider_name": "MockProvider", "context_rules": [], '
            '"summary_rules": [], "holdings_table": null}'
        )
        llm = MockLLMClient(simulate_mode="success", mock_json_response=dummy_json)
    else:
        llm = GeminiLLMClient()

    orchestrator = LearningOrchestrator(repo, llm)
    processor = StatementProcessor(orchestrator, max_workers=4)

    input_dir = Path(input_folder)
    if not input_dir.exists():
        return 0, "Directory does not exist."

    staged_files = []
    for pdf_path in input_dir.glob("*.pdf"):
        file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        staged_files.append((file_hash, str(pdf_path)))

    if not staged_files:
        return 0, "No PDF files found in target directory."

    results = processor.process_batch(staged_files)
    for stmt in results:
        stmt_repo.save_statement(stmt)

    return len(results), "Success"


def main():
    stmt_repo = StatementRepository("data/statements.db")
    ArtifactRepository("data/artifacts.db")

    # ---------------- SIDEBAR: OPERATIONS & CONTROLS ----------------
    with st.sidebar:
        st.markdown("### ⚙️ Pipeline Controls")
        redact_pii = st.toggle("🔒 Mask Client PII (Compliance Mode)", value=True)
        st.divider()

        st.markdown("#### 1. Live Gmail Ingestion")
        if st.button("📩 Sync Unread Emails (IMAP)", use_container_width=True):
            with st.spinner("Connecting to imap.gmail.com..."):
                try:
                    collect_unread_emails()
                    st.success("Gmail sync completed! Check data/staging.")
                except Exception as e:
                    st.error(f"IMAP Error: {e}")

        st.markdown("#### 2. Execute Parser Engine")
        target_dir = st.selectbox(
            "Target Input Directory",
            ["data/staging", "tests/fixtures/raw_pdfs"],
        )
        if st.button("🚀 Run Parser Pipeline", type="primary", use_container_width=True):
            with st.spinner(f"Processing PDFs in {target_dir}..."):
                count, msg = run_pipeline_from_ui(target_dir)
                if count > 0:
                    st.success(f"Processed {count} statement(s)!")
                    st.rerun()
                else:
                    st.warning(msg)

        st.divider()
        st.caption("Activv Money — Self-Learning PMS/AIF Parser")

    # ---------------- MAIN HEADER & KPI RIBBON ----------------
    st.markdown(
        '<div class="main-header">📊 Activv Money — PMS & AIF Statement Intelligence</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Self-Learning Layout Recognition • Zero-LLM Deterministic Parsing • Mathematical Reconciliation</div>',
        unsafe_allow_html=True,
    )

    all_statements = stmt_repo.list_statements(status_filter="ALL", limit=200)
    all_artifacts = load_all_artifacts()

    total_stmts = len(all_statements)
    passed_stmts = len([s for s in all_statements if s["status"] == "PASS"])
    quarantined_pending = len(
        [s for s in all_statements if s["status"] != "PASS" and not s["resolved"]]
    )
    active_artifacts = len([a for a in all_artifacts if a["status"] == "ACTIVE"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Processed Statements", total_stmts)
    col2.metric("Verified (PASS)", passed_stmts)
    col3.metric("Active Learned Formats", active_artifacts, help="Parsed with 0 LLM calls")
    col4.metric("Quarantine Queue (Unresolved)", quarantined_pending)

    st.divider()

    # ---------------- NAVIGATION TABS ----------------
    tab_explorer, tab_quarantine, tab_artifacts = st.tabs(
        [
            "🏦 Portfolio & Holdings Explorer",
            "🚨 Human-Attention Quarantine Queue",
            "🧬 Learned Format Artifacts (DB)",
        ]
    )

    # ================= TAB 1: PORTFOLIO EXPLORER =================
    with tab_explorer:
        col_filter, col_select = st.columns([1, 3])
        with col_filter:
            status_filter = st.radio(
                "Filter by Validation Status",
                ["ALL", "PASS", "FAIL"],
                horizontal=True,
            )

        filtered_stmts = (
            all_statements
            if status_filter == "ALL"
            else [s for s in all_statements if s["status"] == status_filter]
        )

        if not filtered_stmts:
            st.info("No statements match the current filter. Run the pipeline from the sidebar.")
        else:
            df_overview = pd.DataFrame(filtered_stmts)
            df_overview["resolved"] = df_overview["resolved"].apply(
                lambda r: "✅ Resolved" if r else "⏳ Pending"
            )
            st.dataframe(
                df_overview[
                    [
                        "statement_id",
                        "provider_name",
                        "status",
                        "resolved",
                        "details",
                        "created_at",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("### 🔍 Deep-Dive Statement Inspector")
            selected_id = st.selectbox(
                "Select Statement ID to Inspect",
                [s["statement_id"] for s in filtered_stmts],
            )

            raw_json = stmt_repo.get_statement_json(selected_id)
            if raw_json:
                data = json.loads(raw_json)
                if redact_pii and "context" in data:
                    data["context"]["client_identifier"] = "*** REDACTED PII ***"

                ctx = data.get("context", {})
                summ = data.get("summary", {})
                val = data.get("validation", {})
                prov = data.get("provenance", {})
                holdings = data.get("holdings", [])

                # Top Context & Validation Banner
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**Provider:**\n{ctx.get('provider_name', 'N/A')}")
                c2.markdown(f"**Client ID:**\n`{ctx.get('client_identifier', 'N/A')}`")
                c3.markdown(f"**Period / Currency:**\n{ctx.get('statement_period', 'N/A')} ({ctx.get('currency', 'INR')})")
                badge_class = "status-pass" if val.get("status") == "PASS" else "status-fail"
                c4.markdown(
                    f"**Validation Status:**<br><span class='{badge_class}'>{val.get('status')}</span>",
                    unsafe_allow_html=True,
                )

                st.info(f"**Reconciliation Diagnostics:** {val.get('details')}")

                # Financial Summary Metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Opening Value", format_inr(summ.get("opening_value", "0")))
                holdings_sum = sum(Decimal(str(h.get("market_value", "0"))) for h in holdings)
                m2.metric("Extracted Holdings Sum", format_inr(str(holdings_sum)))
                m3.metric("Cash Balance", format_inr(summ.get("cash_balance", "0")))
                m4.metric("Closing Value", format_inr(summ.get("closing_value", "0")))

                # Holdings Table
                st.markdown("#### 📈 Extracted Portfolio Holdings")
                if holdings:
                    df_holdings = pd.DataFrame(holdings)
                    st.dataframe(df_holdings, use_container_width=True, hide_index=True)
                else:
                    st.warning("Zero holdings extracted for this statement.")

                with st.expander("🛠️ View Provenance & Canonical JSON Payload"):
                    st.caption(
                        f"Source SHA-256: `{prov.get('source_hash')}` | "
                        f"Layout Fingerprint: `{prov.get('layout_fingerprint')}` | "
                        f"Artifact Version: `{prov.get('artifact_version')}`"
                    )
                    st.json(data)

    # ================= TAB 2: QUARANTINE QUEUE =================
    with tab_quarantine:
        st.markdown("### 🚨 Statements Requiring Human Attention")
        st.caption(
            "Statements fail into quarantine when mathematical reconciliation (Holdings + Cash == Closing) "
            "cannot be verified or when an unfamiliar layout lacks standard tables."
        )

        failed_stmts = [s for s in all_statements if s["status"] != "PASS"]
        if not failed_stmts:
            st.success("🎉 Quarantine queue is completely clear! All statements validated.")
        else:
            for item in failed_stmts:
                with st.container(border=True):
                    q1, q2, q3 = st.columns([3, 4, 2])
                    q1.markdown(f"**ID:** `{item['statement_id']}`\n\n**Provider:** {item['provider_name']}")
                    q2.markdown(
                        f"**Diagnostic Reason:**\n`{item['details']}`\n\n"
                        f"**Timestamp:** {item['created_at']}"
                    )
                    with q3:
                        if item["resolved"]:
                            st.success("✅ Resolved by Operator")
                        else:
                            if st.button(
                                "Mark as Resolved",
                                key=f"resolve_{item['statement_id']}",
                                use_container_width=True,
                            ):
                                stmt_repo.mark_resolved(item["statement_id"])
                                st.rerun()

    # ================= TAB 3: LEARNED ARTIFACTS =================
    with tab_artifacts:
        st.markdown("### 🧬 Persisted Layout Artifacts (`artifacts.db`)")
        st.caption(
            "Declarative JSON extraction rules learned once via Gemini and reused deterministically with zero runtime LLM calls."
        )

        if not all_artifacts:
            st.info("No layout artifacts stored yet.")
        else:
            df_art = pd.DataFrame(all_artifacts)[
                ["id", "provider_name", "status", "fingerprint", "created_at"]
            ]
            st.dataframe(df_art, use_container_width=True, hide_index=True)

            selected_art_id = st.selectbox(
                "Inspect Learned Coordinate JSON Ruleset (by Artifact ID)",
                [a["id"] for a in all_artifacts],
            )
            selected_art = next((a for a in all_artifacts if a["id"] == selected_art_id), None)
            if selected_art:
                st.json(json.loads(selected_art["json_payload"]))


if __name__ == "__main__":
    main()
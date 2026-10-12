import pytest

from parser_app.artifact_repository import ArtifactRepository
from parser_app.artifact_schema import LayoutArtifact
from parser_app.extractor import PDFExtractor
from parser_app.llm_client import MockLLMClient
from parser_app.orchestrator import LearningOrchestrator


@pytest.fixture
def mock_db(tmp_path):
    repo = ArtifactRepository(db_path=str(tmp_path / "drift_test.db"))
    
    # 1. Pre-load an ACTIVE "Version 1" artifact into the database for AlphaWealth
    v1_artifact = LayoutArtifact(
        artifact_version="1.0",
        layout_fingerprint="old_hash_v1",
        provider_name="AlphaWealth Portfolio Management Services",
        context_rules=[], summary_rules=[], holdings_table=None
    )
    cand_id = repo.save_candidate(v1_artifact)
    repo.promote_to_active(cand_id, v1_artifact.provider_name)
    
    return repo

def test_drift_detection_and_deprecation(mock_db):
    """Verify that a drifted layout replaces the old artifact via deprecation."""
    
    # 2. Simulate the LLM successfully learning the NEW "Version 2" layout
    v2_json = """
    {
        "artifact_version": "2.0",
        "layout_fingerprint": "fake_hash",
        "provider_name": "AlphaWealth Portfolio Management Services",
        "context_rules": [],
        "summary_rules": [
            {"name": "opening_value", "label": "Opening", "direction": "right", "offset_words": 2},
            {"name": "closing_value", "label": "Closing", "direction": "right", "offset_words": 2},
            {"name": "cash_balance", "label": "Cash:", "direction": "right", "offset_words": 1}
        ],
        "holdings_table": {
            "start_anchor": "Current Holdings",
            "columns": [
                {"name": "security_name", "x_start": 70, "x_end": 170},
                {"name": "isin", "x_start": 170, "x_end": 240},
                {"name": "quantity", "x_start": 240, "x_end": 290},
                {"name": "market_value", "x_start": 350, "x_end": 450}
            ]
        }
    }
    """
    llm = MockLLMClient(simulate_mode="success", mock_json_response=v2_json)
    orchestrator = LearningOrchestrator(mock_db, llm)
    
    # 3. Pass the actual PDF (which will generate a NEW real hash, simulating drift)
    pdf_pages = PDFExtractor.extract_page_data("tests/fixtures/raw_pdfs/alpha_wealth.pdf")
    
    # 4. Run the document
    stmt, learned = orchestrator.process_document(pdf_pages, "doc_hash")
    
    # Ensure it successfully learned the new v2 layout
    assert learned is True
    assert stmt.validation.status.name == "PASS"
    
    # 5. VERIFY DATABASE STATE
    # The old v1 artifact should be DEPRECATED
    import sqlite3
    with sqlite3.connect(mock_db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM artifacts WHERE fingerprint = 'old_hash_v1'")
        assert cursor.fetchone()[0] == "DEPRECATED"
        
        # There should only be ONE active artifact for AlphaWealth
        cursor.execute("SELECT COUNT(*) FROM artifacts WHERE status = 'ACTIVE' AND provider_name = 'AlphaWealth Portfolio Management Services'")
        assert cursor.fetchone()[0] == 1
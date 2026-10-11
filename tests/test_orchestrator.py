import pytest

from parser_app.artifact_repository import ArtifactRepository
from parser_app.extractor import PDFExtractor
from parser_app.llm_client import MockLLMClient
from parser_app.orchestrator import LearningOrchestrator
from parser_app.schema import ValidationStatus

VALID_PDF = "tests/fixtures/raw_pdfs/alpha_wealth.pdf"

@pytest.fixture
def test_repo(tmp_path):
    db_file = tmp_path / "orch_test.db"
    return ArtifactRepository(db_path=str(db_file))

@pytest.fixture
def pdf_data():
    return PDFExtractor.extract_page_data(VALID_PDF)

def test_successful_learning_loop(test_repo, pdf_data):
    """
    Simulates a perfect LLM generating a perfect artifact.
    The orchestrator should test it, prove the math passes, and promote it.
    """
    # We feed the mock LLM the exact artifact we hand-coded in Phase 6
    perfect_llm_json = """
    {
        "artifact_version": "1.0",
        "layout_fingerprint": "eb60773d5ff6482de5b7d159187320c2d3cf38031dcf7f1e7371d9d9361a5518",
        "provider_name": "AlphaWealth",
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
    mock_llm = MockLLMClient(simulate_mode="success", mock_json_response=perfect_llm_json)
    orchestrator = LearningOrchestrator(test_repo, mock_llm)
    
    # Run the document. It should trigger learning (return True)
    statement, learned = orchestrator.process_document(pdf_data, "hash123")
    
    assert learned is True
    assert statement.validation.status == ValidationStatus.PASS
    
    # Run the document a second time!
    # Because it is in the database as ACTIVE, it should NOT trigger learning (return False)
    statement2, learned2 = orchestrator.process_document(pdf_data, "hash456")
    
    assert learned2 is False # The Golden Rule is proven!

def test_hallucinated_artifact_rejected(test_repo, pdf_data):
    """
    Simulates an LLM hallucinating the wrong coordinates.
    The math should fail, and the candidate should be rejected.
    """
    # The LLM guesses that market value is between X=0 and X=50 (where no data exists)
    bad_llm_json = """
    {
        "artifact_version": "bad.1",
        "layout_fingerprint": "eb60773d5ff6482de5b7d159187320c2d3cf38031dcf7f1e7371d9d9361a5518",
        "provider_name": "AlphaWealth",
        "context_rules": [],
        "summary_rules": [
            {"name": "opening_value", "label": "Opening", "direction": "right", "offset_words": 2},
            {"name": "closing_value", "label": "Closing", "direction": "right", "offset_words": 2},
            {"name": "cash_balance", "label": "Cash:", "direction": "right", "offset_words": 1}
        ],
        "holdings_table": {
            "start_anchor": "Current Holdings",
            "columns": [
                {"name": "market_value", "x_start": 0, "x_end": 50} 
            ]
        }
    }
    """
    mock_llm = MockLLMClient(simulate_mode="success", mock_json_response=bad_llm_json)
    orchestrator = LearningOrchestrator(test_repo, mock_llm)
    
    statement, learned = orchestrator.process_document(pdf_data, "hash123")
    
    # Learning was triggered, but the math failed, so we get the quarantined stub back
    assert learned is True
    assert statement.validation.status == ValidationStatus.FAIL
    assert "rejected" in statement.validation.details
    
    # Verify the database correctly blocked the hallucination from becoming active
    active = test_repo.get_active_artifact("eb60773d5ff6482de5b7d159187320c2d3cf38031dcf7f1e7371d9d9361a5518")
    assert active is None
import pytest

from parser_app.artifact_repository import ArtifactRepository
from parser_app.llm_client import MockLLMClient
from parser_app.orchestrator import LearningOrchestrator
from parser_app.queue_worker import StatementProcessor

VALID_PDF = "tests/fixtures/raw_pdfs/alpha_wealth.pdf"

@pytest.fixture
def blank_orchestrator(tmp_path):
    repo = ArtifactRepository(db_path=str(tmp_path / "queue_test.db"))
    
    # Provide a blank dummy JSON just so the mock LLM returns something
    dummy_json = """
    {
        "artifact_version": "1.0",
        "layout_fingerprint": "fake",
        "provider_name": "AlphaWealth",
        "context_rules": [],
        "summary_rules": [],
        "holdings_table": null
    }
    """
    llm = MockLLMClient(simulate_mode="success", mock_json_response=dummy_json)
    return LearningOrchestrator(repo, llm)

def test_concurrent_batch_processing(blank_orchestrator):
    """Ensure the thread pool safely processes multiple items and gathers results."""
    # Simulate an email arriving with 4 attachments
    staged_files = [
        (f"hash_00{i}", VALID_PDF) for i in range(4)
    ]
    
    # We restrict to 2 workers to force the queue to cycle through the 4 jobs
    processor = StatementProcessor(blank_orchestrator, max_workers=2)
    
    results = processor.process_batch(staged_files)
    
    # All 4 documents must be processed without the orchestrator crashing
    assert len(results) == 4
    
    # Because we gave the LLM a dummy JSON with no extraction rules, 
    # the financial math will fail. This is expected. We just want to ensure 
    # the multi-threading works without thread locks.
    statuses = [stmt.validation.status.name for stmt in results]
    assert "FAIL" in statuses or "NOT_VERIFIABLE" in statuses

def test_worker_isolates_exceptions(blank_orchestrator):
    """Ensure that if one document completely crashes (e.g., deleted file), the rest survive."""
    staged_files = [
        ("hash_good_1", VALID_PDF),
        ("hash_bad_2", "tests/fixtures/raw_pdfs/DOES_NOT_EXIST.pdf"), # This will throw FileNotFoundError
        ("hash_good_3", VALID_PDF)
    ]
    
    processor = StatementProcessor(blank_orchestrator, max_workers=2)
    results = processor.process_batch(staged_files)
    
    # The queue must swallow the FileNotFoundError for hash_bad_2, 
    # and successfully return the 2 good files.
    assert len(results) == 2
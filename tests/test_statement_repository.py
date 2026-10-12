import pytest

from parser_app.schema import ParsedStatement, Provenance, StatementContext, Summary, ValidationResult, ValidationStatus
from parser_app.statement_repository import StatementRepository


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_statements.db"
    return StatementRepository(db_path=str(db_file))

@pytest.fixture
def dummy_statement():
    return ParsedStatement(
        statement_id="TEST-123",
        context=StatementContext(provider_name="TestCorp", strategy_name="N/A", client_identifier="C-01", statement_period="N/A"),
        summary=Summary(opening_value="0", closing_value="0", cash_balance="0"),
        provenance=Provenance(source_hash="abc", layout_fingerprint="def", artifact_version="1.0"),
        validation=ValidationResult(status=ValidationStatus.FAIL, details="Math failed")
    )

def test_save_and_list_statements(repo, dummy_statement):
    repo.save_statement(dummy_statement)
    
    results = repo.list_statements(status_filter="FAIL")
    assert len(results) == 1
    assert results[0]["statement_id"] == "TEST-123"
    assert results[0]["resolved"] == 0

def test_resolve_statement(repo, dummy_statement):
    repo.save_statement(dummy_statement)
    repo.mark_resolved("TEST-123")
    
    results = repo.list_statements()
    assert results[0]["resolved"] == 1
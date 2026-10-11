from decimal import Decimal

import pytest

from parser_app.schema import (
    Holding,
    ParsedStatement,
    Provenance,
    StatementContext,
    Summary,
    ValidationResult,
    ValidationStatus,
)
from parser_app.validator import FinancialValidator


@pytest.fixture
def perfect_statement():
    """A mathematically perfect statement."""
    return ParsedStatement(
        statement_id="TEST-01",
        context=StatementContext(
            provider_name="TestPMS", strategy_name="Growth", 
            client_identifier="C-1", statement_period="Oct"
        ),
        summary=Summary(
            opening_value=Decimal("1000.00"),
            closing_value=Decimal("1050.00"),
            cash_balance=Decimal("50.00")
        ),
        holdings=[
            Holding(security_name="Asset A", quantity=Decimal("10"), market_value=Decimal("500.00")),
            Holding(security_name="Asset B", quantity=Decimal("10"), market_value=Decimal("500.00"))
        ],
        provenance=Provenance(source_hash="x", layout_fingerprint="y", artifact_version="1"),
        validation=ValidationResult(status=ValidationStatus.NOT_VERIFIABLE, details="None")
    )

def test_perfect_statement_passes(perfect_statement):
    """Sum(500 + 500) + Cash(50) == Closing(1050) -> PASS"""
    validated = FinancialValidator.validate(perfect_statement)
    assert validated.validation.status == ValidationStatus.PASS
    assert "Portfolio sum matched" in validated.validation.details

def test_rounding_tolerance_passes(perfect_statement):
    """Sum(500 + 500) + Cash(50) == 1050. Statement closing says 1050.50. Should PASS due to tolerance."""
    perfect_statement.summary.closing_value = Decimal("1050.50")
    validated = FinancialValidator.validate(perfect_statement)
    assert validated.validation.status == ValidationStatus.PASS
    assert "Diff: 0.50" in validated.validation.details

def test_corrupted_data_fails(perfect_statement):
    """Simulate layout drift where a holding value was extracted incorrectly (e.g., missed a zero)."""
    perfect_statement.holdings[0].market_value = Decimal("50.00") # Should be 500
    
    validated = FinancialValidator.validate(perfect_statement)
    assert validated.validation.status == ValidationStatus.FAIL
    assert "Portfolio sum mismatch" in validated.validation.details
    assert "Expected 600.00, got 1050.00" in validated.validation.details

def test_no_holdings_is_not_verifiable(perfect_statement):
    """If there are no holdings, the math cannot be run."""
    perfect_statement.holdings = []
    validated = FinancialValidator.validate(perfect_statement)
    assert validated.validation.status == ValidationStatus.NOT_VERIFIABLE

def test_aif_nav_validation():
    """Test AIF NAV multiplication logic."""
    aif_statement = ParsedStatement(
        statement_id="AIF-01",
        context=StatementContext(
            provider_name="TestAIF", strategy_name="Alt", 
            client_identifier="C-2", statement_period="Oct"
        ),
        summary=Summary(
            opening_value=Decimal("0"), closing_value=Decimal("5200000.00"), 
            cash_balance=Decimal("0"), nav_per_unit=Decimal("10.40")
        ),
        holdings=[
            Holding(security_name="Fund", quantity=Decimal("500000"), market_value=Decimal("5200000.00"))
        ],
        provenance=Provenance(source_hash="x", layout_fingerprint="y", artifact_version="1"),
        validation=ValidationResult(status=ValidationStatus.NOT_VERIFIABLE, details="")
    )
    
    # 500,000 qty * 10.40 NAV == 5,200,000 closing
    validated = FinancialValidator.validate(aif_statement)
    assert validated.validation.status == ValidationStatus.PASS
    assert "AIF NAV matched" in validated.validation.details
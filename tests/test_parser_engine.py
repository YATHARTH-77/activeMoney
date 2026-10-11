import pytest
from parser_app.extractor import PDFExtractor
from parser_app.artifact_schema import (
    LayoutArtifact, ExtractionRule, TableDefinition, ColumnDefinition
)
from parser_app.parser_engine import DeterministicParser
from decimal import Decimal

VALID_PDF = "tests/fixtures/raw_pdfs/alpha_wealth.pdf"

@pytest.fixture
def alpha_artifact():
    return LayoutArtifact(
        artifact_version="1.0",
        layout_fingerprint="alpha_v1",
        provider_name="AlphaWealth",
        context_rules=[
            ExtractionRule(
                name="client_identifier", label="Client:", direction="right", offset_words=1
            ),
            ExtractionRule(
                name="statement_period", label="Period:", direction="right", offset_words=1
            ),
        ],
        summary_rules=[
            ExtractionRule(
                name="opening_value", label="Opening", direction="right", offset_words=2
            ),
            ExtractionRule(
                name="closing_value", label="Closing", direction="right", offset_words=2
            ),
            ExtractionRule(
                name="cash_balance", label="Cash:", direction="right", offset_words=1
            ),
        ],
        holdings_table=TableDefinition(
            start_anchor="Current Holdings",
            columns=[
                # Tightly calibrated X-boundaries to prevent column overlap
                ColumnDefinition(name="security_name", x_start=70, x_end=170),
                ColumnDefinition(name="isin", x_start=170, x_end=240),
                ColumnDefinition(name="quantity", x_start=240, x_end=290),
                ColumnDefinition(name="cost", x_start=290, x_end=350),
                ColumnDefinition(name="market_value", x_start=350, x_end=450),
                ColumnDefinition(name="weight", x_start=450, x_end=580),
            ]
        )
    )


def test_alpha_wealth_parsing(alpha_artifact):
    """Verify the deterministic engine perfectly parses the PDF using the geometric artifact."""
    pages = PDFExtractor.extract_page_data(VALID_PDF)
    parser = DeterministicParser(artifact=alpha_artifact)
    
    parsed_statement = parser.parse(pages, source_hash="test1234")
    
    # 1. Context validation
    assert parsed_statement.context.client_identifier == "CLIENT-A01"
    assert parsed_statement.context.statement_period == "Oct" 
    
    # 2. Summary validation
    assert parsed_statement.summary.opening_value == Decimal("1000000.00")
    assert parsed_statement.summary.closing_value == Decimal("1050000.00")
    assert parsed_statement.summary.cash_balance == Decimal("50000.00")
    
    # 3. Table validation
    assert len(parsed_statement.holdings) == 2
    assert parsed_statement.holdings[0].security_name == "Reliance Ind"
    assert parsed_statement.holdings[0].isin == "INE002A01018"
    assert parsed_statement.holdings[0].market_value == Decimal("510000.00")
    assert parsed_statement.holdings[1].security_name == "HDFC Bank"
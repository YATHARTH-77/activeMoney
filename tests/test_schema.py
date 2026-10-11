import json
from decimal import Decimal
from pathlib import Path

from parser_app.schema import Holding, ParsedStatement


def test_load_synthetic_fixture():
    """Verify that we can load a complete JSON fixture into our Pydantic models."""
    fixture_path = Path("tests/fixtures/synthetic_canonical_1.json")
    
    with open(fixture_path, "r") as f:
        data = json.load(f)
        
    statement = ParsedStatement(**data)
    
    # Assertions to ensure types were cast correctly
    assert statement.context.provider_name == "MockWealth PMS"
    assert statement.summary.closing_value == Decimal("1050000.00")
    assert statement.holdings[0].market_value == Decimal("510000.00")
    assert statement.transactions[0].transaction_type.value == "dividend"

def test_decimal_casting():
    """Verify Pydantic correctly casts string financial inputs to Decimals."""
    holding = Holding(
        security_name="Test Stock",
        quantity="100.5",
        market_value="5000.75"
    )
    assert isinstance(holding.quantity, Decimal)
    assert isinstance(holding.market_value, Decimal)
    assert holding.market_value == Decimal("5000.75")
import json
import os

from parser_app.schema import ParsedStatement


def test_pdfs_exist():
    """Verify the generation script was run and PDFs exist."""
    pdf_dir = "tests/fixtures/raw_pdfs"
    assert os.path.exists(f"{pdf_dir}/alpha_wealth.pdf")
    assert os.path.exists(f"{pdf_dir}/beta_aif.pdf")
    assert os.path.exists(f"{pdf_dir}/gamma_multipage.pdf")

def test_expected_jsons_match_schema():
    """Verify our ground-truth JSONs strictly match the Phase 3 Pydantic schema."""
    json_dir = "tests/fixtures/expected"
    files = ["alpha_wealth.json", "beta_aif.json", "gamma_multipage.json"]
    
    for filename in files:
        with open(f"{json_dir}/{filename}", "r") as f:
            data = json.load(f)
            # This will raise a ValidationError if the JSON is malformed
            statement = ParsedStatement(**data)
            assert statement.statement_id is not None
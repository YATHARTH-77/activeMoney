import os

import pytest

from parser_app.artifact_schema import LayoutArtifact
from parser_app.gemini_client import GeminiLLMClient
from parser_app.llm_client import LearningRequest


# This marker ensures this test ONLY runs when we explicitly ask it to via CLI.
@pytest.mark.integration
def test_real_gemini_api_call():
    """Verify that the real Gemini API can successfully generate a valid LayoutArtifact."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_real_api_key_here":
        pytest.skip("GEMINI_API_KEY not set in .env. Skipping live integration test.")
        
    client = GeminiLLMClient()
    
    # We provide a highly simplified synthetic string to keep the LLM fast and cheap
    req = LearningRequest(
        layout_fingerprint="test_integration_v1",
        structural_text="account summary holdings",
        sample_page_text="Account Summary\nOpening Value: 1000.00\nClosing Value: 1500.00\n\nCurrent Holdings\nSecurity ISIN Quantity\nAAPL US0378331005 100",
        provider_hint="IntegrationTestPMS"
    )
    
    # This calls the REAL API!
    artifact = client.learn_layout(req)
    
    assert isinstance(artifact, LayoutArtifact)
    assert artifact.provider_name == "IntegrationTestPMS"
    assert artifact.layout_fingerprint == "test_integration_v1"
    # Ensure the LLM understood to create a table definition
    assert artifact.holdings_table is not None
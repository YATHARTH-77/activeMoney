import pytest

from parser_app.artifact_schema import LayoutArtifact
from parser_app.llm_client import LearningRequest, LLMError, LLMTimeoutError, LLMValidationError, MockLLMClient, clean_llm_json


@pytest.fixture
def learning_request():
    return LearningRequest(
        layout_fingerprint="mock_v1",
        structural_text="portfolio summary current holdings",
        sample_page_text="Client: 123 \n Current Holdings \n AAPL 100",
        provider_hint="MockWealth"
    )

@pytest.fixture
def perfect_llm_json():
    # A perfectly formatted JSON matching our LayoutArtifact schema
    return """
    {
        "artifact_version": "1.0",
        "layout_fingerprint": "mock_v1",
        "provider_name": "MockWealth",
        "context_rules": [],
        "summary_rules": [],
        "holdings_table": {
            "start_anchor": "Current Holdings",
            "columns": [{"name": "security_name", "x_start": 0, "x_end": 100}]
        }
    }
    """

def test_json_cleaner():
    """Ensure we strip markdown wrappers commonly added by GPT/Claude."""
    messy = "```json\n{\"key\": \"value\"}\n```"
    clean = clean_llm_json(messy)
    assert clean == '{"key": "value"}'

def test_mock_success(learning_request, perfect_llm_json):
    """A perfect LLM response should successfully parse into a LayoutArtifact object."""
    client = MockLLMClient(simulate_mode="success", mock_json_response=perfect_llm_json)
    artifact = client.learn_layout(learning_request)
    
    assert isinstance(artifact, LayoutArtifact)
    assert artifact.provider_name == "MockWealth"
    assert len(artifact.holdings_table.columns) == 1

def test_mock_timeout(learning_request):
    """The pipeline must safely catch network timeouts."""
    client = MockLLMClient(simulate_mode="timeout")
    with pytest.raises(LLMTimeoutError):
        client.learn_layout(learning_request)

def test_mock_refusal(learning_request):
    """The pipeline must safely catch safety/policy refusals."""
    client = MockLLMClient(simulate_mode="refusal")
    with pytest.raises(LLMError, match="I cannot process"):
        client.learn_layout(learning_request)

def test_mock_malformed_json_syntax(learning_request):
    """The pipeline must catch completely broken JSON (missing quotes/brackets)."""
    bad_json = "{ provider_name: 'Missing Quotes, broken JSON } "
    client = MockLLMClient(simulate_mode="success", mock_json_response=bad_json)
    
    with pytest.raises(LLMValidationError, match="invalid JSON syntax"):
        client.learn_layout(learning_request)

def test_mock_schema_violation(learning_request):
    """The pipeline must catch valid JSON that is missing required fields."""
    # Valid JSON, but missing 'artifact_version' and 'layout_fingerprint'
    missing_fields_json = '{"provider_name": "MockWealth"}'
    client = MockLLMClient(simulate_mode="success", mock_json_response=missing_fields_json)
    
    with pytest.raises(LLMValidationError, match="violated the required schema"):
        client.learn_layout(learning_request)
import json
import re
from typing import Optional, Protocol

from pydantic import BaseModel, ValidationError

from parser_app.artifact_schema import LayoutArtifact


class LLMError(Exception):
    """Base exception for all LLM interaction failures."""
    pass

class LLMTimeoutError(LLMError):
    """Raised when the LLM API takes too long to respond."""
    pass

class LLMValidationError(LLMError):
    """Raised when the LLM returns invalid JSON or violates the Pydantic schema."""
    pass

class LearningRequest(BaseModel):
    """The exact evidence sent to the LLM to teach it a new format."""
    layout_fingerprint: str
    structural_text: str
    sample_page_text: str
    provider_hint: Optional[str] = None
    prompt_version: str = "v1.0"

class LLMClient(Protocol):
    """Protocol defining how our system interacts with ANY language model."""
    def learn_layout(self, request: LearningRequest) -> LayoutArtifact:
        ...

def clean_llm_json(raw_response: str) -> str:
    """Safely strips markdown formatting commonly hallucinated by LLMs."""
    # Remove ```json and ``` wrapping
    cleaned = re.sub(r'^```(?:json)?\n', '', raw_response.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r'\n```$', '', cleaned.strip())
    return cleaned.strip()

class MockLLMClient:
    """
    A deterministic, offline fake LLM for rigorous testing.
    Can be configured to simulate timeouts, hallucinations, or perfect responses.
    """
    def __init__(self, simulate_mode: str = "success", mock_json_response: str = ""):
        self.simulate_mode = simulate_mode
        self.mock_json_response = mock_json_response

    def learn_layout(self, request: LearningRequest) -> LayoutArtifact:
        if self.simulate_mode == "timeout":
            raise LLMTimeoutError("Mock LLM simulated a network timeout.")
            
        if self.simulate_mode == "refusal":
            raise LLMError("I'm sorry, I cannot process financial data.")

        # Clean the mock response just like we would a real one
        raw_json_str = clean_llm_json(self.mock_json_response)
        
        try:
            # First, check if it's even valid JSON
            json.loads(raw_json_str) 
            # Second, enforce strict schema validation
            artifact = LayoutArtifact.model_validate_json(raw_json_str)
            return artifact
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"LLM hallucinated invalid JSON syntax: {e}")
        except ValidationError as e:
            raise LLMValidationError(f"LLM output violated the required schema: {e}")
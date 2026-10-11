import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from parser_app.artifact_schema import LayoutArtifact
from parser_app.llm_client import LearningRequest, LLMError, LLMValidationError, clean_llm_json

# Load environment variables from .env file securely
load_dotenv()

class GeminiLLMClient:
    # Upgraded to Gemini 3.8 Flash per the Google API deprecation notice
    def __init__(self, api_key: str = None, model_name: str = "gemini-3.8-flash"):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key or key == "your_real_api_key_here":
            raise ValueError("GEMINI_API_KEY environment variable is missing or invalid.")
        
        self.client = genai.Client(api_key=key)
        self.model_name = model_name

    def learn_layout(self, request: LearningRequest) -> LayoutArtifact:
        prompt = self._build_prompt(request)
        try:
            # Force the model to output strict JSON
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            raw_text = response.text
        except Exception as e:
            raise LLMError(f"Gemini API request failed: {str(e)}")

        cleaned_json = clean_llm_json(raw_text)
        
        try:
            return LayoutArtifact.model_validate_json(cleaned_json)
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Gemini hallucinated invalid JSON syntax: {e}")
        except ValidationError as e:
            raise LLMValidationError(f"Gemini output violated schema constraints: {e}")

    def _build_prompt(self, request: LearningRequest) -> str:
        """Constructs a highly constrained prompt using Pydantic's automatic JSON schema."""
        schema_json = json.dumps(LayoutArtifact.model_json_schema(), indent=2)
        
        return f"""
        You are an elite, deterministic data extraction architect building parsing configurations.
        Your task is to analyze the following sample text from a financial statement and generate a JSON ruleset that will allow a deterministic script to extract the data in the future.
        
        Context Hints:
        Provider Name: {request.provider_hint or 'Unknown'}
        Layout Fingerprint: {request.layout_fingerprint}
        
        CRITICAL RULES:
        1. You must output ONLY valid JSON.
        2. The JSON must exactly match the schema provided below.
        3. Do not include markdown code block formatting.
        4. For table extraction rules, use geometric X-coordinates (x_start, x_end) that realistically map to columns, assuming a standard letter page width is 612 pixels.
        
        EXPECTED STRICT JSON SCHEMA:
        {schema_json}
        
        STRUCTURAL BOILERPLATE OVERVIEW (For context):
        {request.structural_text}
        
        SAMPLE STATEMENT TEXT:
        {request.sample_page_text}
        """
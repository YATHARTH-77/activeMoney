import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from parser_app.artifact_schema import LayoutArtifact
from parser_app.llm_client import LearningRequest, LLMError, LLMValidationError, clean_llm_json

load_dotenv()

class GeminiLLMClient:
    def __init__(self, api_key: str = None, model_name: str = "gemini-3.8-flash"):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key or key == "your_real_api_key_here":
            raise ValueError("GEMINI_API_KEY environment variable is missing or invalid.")
        
        self.client = genai.Client(api_key=key)
        self.model_name = model_name

    @retry(
        wait=wait_exponential(multiplier=2, min=2, max=10),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _call_api_with_retry(self, prompt: str):
        return self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

    def learn_layout(self, request: LearningRequest) -> LayoutArtifact:
        prompt = self._build_prompt(request)
        try:
            response = self._call_api_with_retry(prompt)
            raw_text = response.text
        except Exception as e:
            raise LLMError(f"Gemini API request failed after retries: {str(e)}")

        cleaned_json = clean_llm_json(raw_text)
        
        try:
            return LayoutArtifact.model_validate_json(cleaned_json)
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Gemini hallucinated invalid JSON syntax: {e}")
        except ValidationError as e:
            raise LLMValidationError(f"Gemini output violated schema constraints: {e}")

    def _build_prompt(self, request: LearningRequest) -> str:
        schema_json = json.dumps(LayoutArtifact.model_json_schema(), indent=2)
        
        return f"""
        You are an elite, deterministic data extraction architect building parsing configurations.
        Your task is to analyze the following sample text from a financial statement and generate a JSON ruleset that will allow a deterministic script to extract the data in the future.
        
        Context Hints:
        Provider Name: {request.provider_hint or 'Unknown'}
        Layout Fingerprint: {request.layout_fingerprint}
        
        CRITICAL RULES:
        1. You must output ONLY valid JSON. Do NOT wrap it in markdown code blocks.
        2. The JSON must exactly match the schema provided below.
        3. For 'start_anchor' in tables, pick the exact unique phrase that appears right before the table headers (e.g., "Current Holdings" or "Portfolio Summary").
        4. For table extraction rules, use geometric X-coordinates (x_start, x_end) that realistically map to columns. ADD PADDING to the boundaries! (e.g., if a word is [X: 70.0 -> 140.0], make the column x_start: 60, x_end: 160).
        5. EXTREMELY IMPORTANT: For summary/context rules, carefully calculate 'offset_words'. This is the number of words between the label and the target value.
           - Example A: Text is "Opening Value: 1000.00". If label is "Opening", target is "1000.00". The offset_words MUST BE 2 (skipping "Value:").
           - Example B: Text is "Cash: 50.00". If label is "Cash:", target is "50.00". The offset_words MUST BE 1.
        
        EXPECTED STRICT JSON SCHEMA:
        {schema_json}
        
        STRUCTURAL BOILERPLATE OVERVIEW (For context):
        {request.structural_text}
        
        SAMPLE STATEMENT TEXT (With Physical X/Y Coordinates for Mapping):
        {request.sample_page_text}
        """
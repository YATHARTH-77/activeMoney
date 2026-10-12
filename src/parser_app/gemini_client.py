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
            raise LLMValidationError(f"Gemini output invalid JSON syntax: {e}")
        except ValidationError as e:
            raise LLMValidationError(f"Gemini output violated schema constraints: {e}")

    def _build_prompt(self, request: LearningRequest) -> str:
        schema_json = json.dumps(LayoutArtifact.model_json_schema(), indent=2)
        
        return f"""
        You are an elite, deterministic document parsing architect.
        Analyze the spatial text of this financial statement and output a valid JSON configuration artifact.

        Context:
        Provider Hint: {request.provider_hint or 'Unknown'}

        EXTRACTION DIRECTIVES:
        1. Output ONLY valid JSON matching the schema below. No markdown wrappers.
        2. 'provider_name': Extract the institution or fund house name.
        3. 'summary_rules': Provide simple single-word anchor labels:
           - opening_value: label="Opening"
           - closing_value: label="Closing"
           - cash_balance: label="Cash"
        4. 'holdings_table':
           - 'start_anchor': The title string preceding the table (e.g. "HOLDINGS LEDGER", "PORTFOLIO HOLDINGS", "Current Holdings").
           - 'columns': Define the columns based on the sample coordinates:
             * 'security_name' (covers the description text)
             * 'isin' (covers the ISIN identifier)
             * 'quantity' (covers unit counts)
             * 'cost' (covers avg cost/purchase price)
             * 'market_value' (covers total valuation)
             Assign x_start and x_end using the bounding boxes in the sample.

        TARGET SCHEMA:
        {schema_json}

        DOCUMENT TEXT SAMPLE (With coordinates):
        {request.sample_page_text}
        """
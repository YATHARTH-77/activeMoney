import os
import json
from groq import Groq
from pydantic import ValidationError
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from parser_app.llm_client import (
    LearningRequest, LLMError, LLMValidationError, clean_llm_json
)
from parser_app.artifact_schema import LayoutArtifact

load_dotenv()

class GroqLLMClient:
    def __init__(self, api_key: str = None, model_name: str = "openai/gpt-oss-20b"):
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key or key == "your_groq_api_key_here":
            raise ValueError("GROQ_API_KEY environment variable is missing or invalid.")
        
        self.client = Groq(api_key=key)
        self.model_name = model_name

    @retry(
        wait=wait_exponential(multiplier=2, min=2, max=10),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _call_api_with_retry(self, prompt: str):
        # Groq Llama 3 requires explicit JSON Object formatting
        return self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an elite, deterministic document parsing architect. You must output ONLY valid JSON."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )

    def learn_layout(self, request: LearningRequest) -> LayoutArtifact:
        prompt = self._build_prompt(request)
        try:
            response = self._call_api_with_retry(prompt)
            raw_text = response.choices[0].message.content
        except Exception as e:
            raise LLMError(f"Groq API request failed after retries: {str(e)}")

        cleaned_json = clean_llm_json(raw_text)
        
        try:
            return LayoutArtifact.model_validate_json(cleaned_json)
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Groq output invalid JSON syntax: {e}")
        except ValidationError as e:
            raise LLMValidationError(f"Groq output violated schema constraints: {e}")

    def _build_prompt(self, request: LearningRequest) -> str:
        schema_json = json.dumps(LayoutArtifact.model_json_schema(), indent=2)
        
        return f"""
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
           - 'start_anchor': The title string preceding the table (e.g. "HOLDINGS LEDGER", "PORTFOLIO HOLDINGS").
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
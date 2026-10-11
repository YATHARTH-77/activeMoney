from typing import List, Dict, Any, Tuple
import logging

from parser_app.schema import ParsedStatement, ValidationStatus
from parser_app.artifact_schema import LayoutArtifact
from parser_app.artifact_repository import ArtifactRepository, ArtifactStatus
from parser_app.fingerprinter import LayoutFingerprinter, LayoutSignature, FingerprintMatch
from parser_app.llm_client import LLMClient, LearningRequest, LLMError
from parser_app.parser_engine import DeterministicParser
from parser_app.validator import FinancialValidator

logger = logging.getLogger(__name__)

class LearningOrchestrator:
    def __init__(self, repo: ArtifactRepository, llm_client: LLMClient):
        self.repo = repo
        self.llm_client = llm_client

    def process_document(
        self, pdf_pages: List[Dict[str, Any]], source_hash: str
    ) -> Tuple[ParsedStatement, bool]:
        """
        Orchestrates the entire flow. Returns the parsed statement and a boolean 
        indicating if learning was triggered (True) or if it was parsed deterministically (False).
        """
        # 1. Observe and Fingerprint
        signature = LayoutFingerprinter.observe(pdf_pages)
        
        # 2. Check if we know this layout
        active_artifact = self.repo.get_active_artifact(signature.fingerprint_hash)
        
        if active_artifact:
            # GOLDEN RULE: We know this format. ZERO LLM CALLS.
            return self._parse_and_validate(pdf_pages, active_artifact, source_hash), False
            
        # 3. Layout is Unknown. Trigger Learning Phase.
        logger.info(f"Unknown layout detected: {signature.fingerprint_hash}. Initiating learning...")
        learned_artifact = self._execute_learning_loop(pdf_pages, signature)
        
        if not learned_artifact:
            # Learning failed or was rejected by math. Return a dummy quarantined statement.
            return self._create_quarantined_stub(source_hash, signature), True
            
        # 4. Learning succeeded. Parse with the newly promoted artifact.
        return self._parse_and_validate(pdf_pages, learned_artifact, source_hash), True

    def _execute_learning_loop(
        self, pdf_pages: List[Dict[str, Any]], signature: LayoutSignature
    ) -> LayoutArtifact | None:
        """Asks LLM for candidate, tests it via math, and promotes if successful."""
        
        req = LearningRequest(
            layout_fingerprint=signature.fingerprint_hash,
            structural_text=signature.structural_text,
            sample_page_text=pdf_pages[0]["text"] 
        )
        
        try:
            candidate_artifact = self.llm_client.learn_layout(req)
        except LLMError as e:
            logger.error(f"LLM Learning failed: {e}")
            return None
            
        # CRITICAL FIX: The LLM cannot be trusted to return the correct fingerprint hash.
        # We must overwrite whatever the LLM returned with the mathematically proven hash
        # calculated by our Fingerprinter in Step 1.
        candidate_artifact.layout_fingerprint = signature.fingerprint_hash
            
        # Save to DB as a quarantined CANDIDATE
        cand_id = self.repo.save_candidate(candidate_artifact)
        
        # HYPOTHESIS TEST: Run the deterministic parser using this untrusted candidate
        test_statement = self._parse_and_validate(pdf_pages, candidate_artifact, "test_hash")
        
        if test_statement.validation.status == ValidationStatus.PASS:
            # The math proved the LLM was correct! Promote it.
            self.repo.promote_to_active(cand_id, signature.fingerprint_hash)
            logger.info("Candidate validated and promoted to ACTIVE.")
            return candidate_artifact
        else:
            # The LLM hallucinated bad coordinates. Reject it to protect the database.
            logger.warning(
                f"Candidate rejected due to financial mismatch: {test_statement.validation.details}"
            )
            self._mark_rejected(cand_id)
            return None

    def _parse_and_validate(
        self, pdf_pages: List[Dict[str, Any]], artifact: LayoutArtifact, source_hash: str
    ) -> ParsedStatement:
        parser = DeterministicParser(artifact)
        statement = parser.parse(pdf_pages, source_hash)
        return FinancialValidator.validate(statement)
        
    def _mark_rejected(self, artifact_id: int):
        import sqlite3
        with sqlite3.connect(self.repo.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE artifacts SET status = ? WHERE id = ?", 
                (ArtifactStatus.REJECTED.value, artifact_id)
            )
            conn.commit()

    def _create_quarantined_stub(self, source_hash: str, sig: LayoutSignature) -> ParsedStatement:
        from parser_app.schema import StatementContext, Summary, Provenance, ValidationResult
        return ParsedStatement(
            statement_id=f"QUAR-{source_hash[:8]}",
            context=StatementContext(provider_name="Unknown", strategy_name="N/A", client_identifier="N/A", statement_period="N/A"),
            summary=Summary(opening_value="0", closing_value="0", cash_balance="0"),
            provenance=Provenance(source_hash=source_hash, layout_fingerprint=sig.fingerprint_hash, artifact_version="none"),
            validation=ValidationResult(status=ValidationStatus.FAIL, details="Learning phase failed or rejected.")
        )
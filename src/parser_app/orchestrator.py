import logging
from typing import Any, Dict, List, Tuple

from parser_app.artifact_repository import ArtifactRepository, ArtifactStatus
from parser_app.artifact_schema import LayoutArtifact
from parser_app.fingerprinter import LayoutFingerprinter, LayoutSignature
from parser_app.llm_client import LearningRequest, LLMClient, LLMError
from parser_app.parser_engine import DeterministicParser
from parser_app.schema import ParsedStatement, ValidationStatus
from parser_app.validator import FinancialValidator

logger = logging.getLogger(__name__)


class LearningOrchestrator:
    def __init__(self, repo: ArtifactRepository, llm_client: LLMClient):
        self.repo = repo
        self.llm_client = llm_client

    def process_document(
        self, pdf_pages: List[Dict[str, Any]], source_hash: str
    ) -> Tuple[ParsedStatement, bool]:
        signature = LayoutFingerprinter.observe(pdf_pages)
        active_artifact = self.repo.get_active_artifact(signature.fingerprint_hash)

        if active_artifact:
            return self._parse_and_validate(pdf_pages, active_artifact, source_hash), False

        full_text = "\n".join(p.get("text", "") for p in pdf_pages)
        drift_provider = self._detect_drift_provider(full_text)

        if drift_provider:
            logger.info(
                f"Layout DRIFT detected for known provider: {drift_provider}. Triggering recovery learning..."
            )
        else:
            logger.info(
                f"Unknown layout detected: {signature.fingerprint_hash}. Initiating learning..."
            )

        learned_artifact = self._execute_learning_loop(pdf_pages, signature, drift_provider)

        if not learned_artifact:
            return self._create_quarantined_stub(source_hash, signature), True

        return self._parse_and_validate(pdf_pages, learned_artifact, source_hash), True

    def _detect_drift_provider(self, pdf_text: str) -> str | None:
        all_active = self.repo.get_all_active_artifacts()
        pdf_text_lower = pdf_text.lower()
        for art in all_active:
            if art.provider_name.lower() in pdf_text_lower and art.provider_name != "Unknown":
                return art.provider_name
        return None

    def _execute_learning_loop(
        self,
        pdf_pages: List[Dict[str, Any]],
        signature: LayoutSignature,
        provider_hint: str = None,
    ) -> LayoutArtifact | None:
        # MULTI-PAGE SPATIAL SAMPLING:
        # Sample spatial coordinates across up to 4 pages so the LLM sees cover pages,
        # multi-page table continuations, and late-page summaries.
        spatial_lines = []
        for page_idx, page in enumerate(pdf_pages[:4]):
            page_words = page.get("words", [])
            spatial_lines.append(f"--- PAGE {page_idx + 1} SPATIAL SAMPLE ---")
            for w in page_words[:450]:
                spatial_lines.append(
                    f"[P{page_idx + 1} | X: {w['x0']:.1f} -> {w['x1']:.1f}, Y: {w['top']:.1f}] {w['text']}"
                )
        spatial_text = "\n".join(spatial_lines)

        req = LearningRequest(
            layout_fingerprint=signature.fingerprint_hash,
            structural_text=signature.structural_text,
            sample_page_text=spatial_text,
            provider_hint=provider_hint,
        )

        try:
            candidate_artifact = self.llm_client.learn_layout(req)
        except LLMError as e:
            logger.error(f"LLM Learning failed: {e}")
            return None

        candidate_artifact.layout_fingerprint = signature.fingerprint_hash
        cand_id = self.repo.save_candidate(candidate_artifact)

        test_statement = self._parse_and_validate(pdf_pages, candidate_artifact, "test_hash")

        if test_statement.validation.status == ValidationStatus.PASS:
            self.repo.promote_to_active(cand_id, candidate_artifact.provider_name)
            logger.info(
                f"Candidate validated and promoted to ACTIVE for provider {candidate_artifact.provider_name}."
            )
            return candidate_artifact
        else:
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
                (ArtifactStatus.REJECTED.value, artifact_id),
            )
            conn.commit()

    def _create_quarantined_stub(
        self, source_hash: str, sig: LayoutSignature
    ) -> ParsedStatement:
        from parser_app.schema import (
            Provenance,
            StatementContext,
            Summary,
            ValidationResult,
        )

        return ParsedStatement(
            statement_id=f"QUAR-{source_hash[:8]}",
            context=StatementContext(
                provider_name="Unknown",
                strategy_name="N/A",
                client_identifier="N/A",
                statement_period="N/A",
            ),
            summary=Summary(opening_value="0", closing_value="0", cash_balance="0"),
            provenance=Provenance(
                source_hash=source_hash,
                layout_fingerprint=sig.fingerprint_hash,
                artifact_version="none",
            ),
            validation=ValidationResult(
                status=ValidationStatus.FAIL,
                details="Learning phase failed or rejected.",
            ),
        )
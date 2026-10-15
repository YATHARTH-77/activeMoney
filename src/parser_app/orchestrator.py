import logging
import re
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
    def __init__(self, repo: ArtifactRepository, llm_clients: List[LLMClient] | LLMClient):
        self.repo = repo
        self.llm_clients = llm_clients if isinstance(llm_clients, list) else [llm_clients]

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
        spatial_lines = []
        for page_idx, page in enumerate(pdf_pages[:3]):
            words = page.get("words", [])
            spatial_lines.append(f"--- PAGE {page_idx + 1} ---")
            lines_dict: Dict[float, List[Dict[str, Any]]] = {}
            for w in words:
                matched_top = None
                for top in lines_dict.keys():
                    if abs(w["top"] - top) < 3.5:
                        matched_top = top
                        break
                if matched_top is not None:
                    lines_dict[matched_top].append(w)
                else:
                    lines_dict[w["top"]] = [w]

            for top in sorted(lines_dict.keys())[:35]:
                lw = sorted(lines_dict[top], key=lambda i: i["x0"])
                tokens = [f"X:{w['x0']:.0f}-{w['x1']:.0f} '{w['text']}'" for w in lw]
                spatial_lines.append(f"[Y:{top:.0f}] " + " | ".join(tokens))

        spatial_text = "\n".join(spatial_lines)

        req = LearningRequest(
            layout_fingerprint=signature.fingerprint_hash,
            structural_text=signature.structural_text,
            sample_page_text=spatial_text,
            provider_hint=provider_hint,
        )

        for llm in self.llm_clients:
            provider_name = llm.__class__.__name__
            try:
                candidate_artifact = llm.learn_layout(req)

                # Clean hallucinated brackets or metadata from start_anchor
                if candidate_artifact.holdings_table:
                    candidate_artifact.holdings_table.start_anchor = re.sub(
                        r"\[[^\]]*\]", "", candidate_artifact.holdings_table.start_anchor
                    ).strip()

                candidate_artifact.layout_fingerprint = signature.fingerprint_hash
                cand_id = self.repo.save_candidate(candidate_artifact)

                test_statement = self._parse_and_validate(pdf_pages, candidate_artifact, "test_hash")

                if test_statement.validation.status == ValidationStatus.PASS:
                    self.repo.promote_to_active(cand_id, candidate_artifact.provider_name)
                    logger.info(f"✅ [{provider_name}] Candidate validated and promoted to ACTIVE!")
                    return candidate_artifact
                else:
                    logger.warning(
                        f"❌ [{provider_name}] Candidate failed math validation. Details: {test_statement.validation.details}"
                    )
                    self._mark_rejected(cand_id)
            except LLMError as e:
                logger.error(f"❌ [{provider_name}] API Error: {e}")
                continue

        logger.error("🛑 All LLM providers failed to generate a mathematically valid artifact.")
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
                details="All LLM providers failed learning phase.",
            ),
        )
import concurrent.futures
import logging
from typing import List, Tuple

from parser_app.extractor import PDFExtractor
from parser_app.orchestrator import LearningOrchestrator
from parser_app.schema import ParsedStatement

logger = logging.getLogger(__name__)

class StatementProcessor:
    def __init__(self, orchestrator: LearningOrchestrator, max_workers: int = 4):
        self.orchestrator = orchestrator
        self.max_workers = max_workers

    def process_batch(self, staged_files: List[Tuple[str, str]]) -> List[ParsedStatement]:
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_hash = {
                executor.submit(self._process_single, file_hash, file_path): file_hash 
                for file_hash, file_path in staged_files
            }
            
            for future in concurrent.futures.as_completed(future_to_hash):
                file_hash = future_to_hash[future]
                try:
                    # NEW: 30-second strict timeout limit per document to prevent memory/CPU hangs
                    statement = future.result(timeout=30.0)
                    results.append(statement)
                except concurrent.futures.TimeoutError:
                    logger.error(f"RESOURCE LIMIT EXCEEDED: Document {file_hash} timed out after 30s.")
                except Exception as exc:
                    logger.error(f"FATAL Pipeline Error for document {file_hash}: {exc}")
                    
        return results

    def _process_single(self, file_hash: str, file_path: str) -> ParsedStatement:
        logger.info(f"Worker thread starting job for hash: {file_hash}")
        pdf_pages = PDFExtractor.extract_page_data(file_path)
        statement, learned = self.orchestrator.process_document(pdf_pages, file_hash)
        logger.info(f"Finished {file_hash}. Valid: {statement.validation.status.value}. Learned: {learned}")
        return statement
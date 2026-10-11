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
        """
        Takes a list of (source_hash, file_path) from the ingestor and processes 
        them concurrently. Isolates failures to prevent cascading pipeline crashes.
        """
        results = []
        
        # Creates a bounded pool of threads to prevent RAM exhaustion
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Map the future object to its source_hash so we know which file crashed if it fails
            future_to_hash = {
                executor.submit(self._process_single, file_hash, file_path): file_hash 
                for file_hash, file_path in staged_files
            }
            
            for future in concurrent.futures.as_completed(future_to_hash):
                file_hash = future_to_hash[future]
                try:
                    statement = future.result()
                    results.append(statement)
                except Exception as exc:
                    # DLQ (Dead Letter Queue) Pattern: Trap the error, log it, and move on.
                    logger.error(f"FATAL Pipeline Error for document {file_hash}: {exc}")
                    
        return results

    def _process_single(self, file_hash: str, file_path: str) -> ParsedStatement:
        logger.info(f"Worker thread starting job for hash: {file_hash}")
        
        # 1. Extract physical coordinates
        pdf_pages = PDFExtractor.extract_page_data(file_path)
        
        # 2. Run the full AI/DB learning lifecycle
        statement, learned = self.orchestrator.process_document(pdf_pages, file_hash)
        
        logger.info(f"Finished {file_hash}. Valid: {statement.validation.status.value}. Learned: {learned}")
        return statement
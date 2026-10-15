import concurrent.futures
import logging
import time
from dataclasses import dataclass
from typing import List, Tuple
import pdfplumber

from parser_app.schema import ParsedStatement

logger = logging.getLogger(__name__)

@dataclass
class PipelineMetrics:
    total_processing_time: float = 0.0
    documents_processed: int = 0
    success_count: int = 0
    quarantine_count: int = 0

class StatementProcessor:
    def __init__(self, orchestrator, max_workers: int = 4):
        self.orchestrator = orchestrator
        self.max_workers = max_workers
        self.metrics = PipelineMetrics()

    def process_batch(self, staged_files: List[Tuple[str, str]]) -> List[ParsedStatement]:
        results = []
        start_time = time.perf_counter()
        
        # Advanced Parallel Execution Pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_doc = {
                executor.submit(self._process_single, file_hash, file_path): (file_hash, file_path) 
                for file_hash, file_path in staged_files
            }
            
            for future in concurrent.futures.as_completed(future_to_doc):
                file_hash, file_path = future_to_doc[future]
                try:
                    stmt, was_learned = future.result()
                    results.append(stmt)
                    
                    # Update thread-safe metrics
                    if stmt.validation.status.name == "PASS":
                        self.metrics.success_count += 1
                    else:
                        self.metrics.quarantine_count += 1
                except Exception as exc:
                    logger.error(f"FATAL Pipeline Error for document {file_hash}: {exc}")
                    
        end_time = time.perf_counter()
        
        # Finalize Observability Metrics
        self.metrics.total_processing_time = end_time - start_time
        self.metrics.documents_processed = len(staged_files)
        
        return results

    def _process_single(self, file_hash: str, file_path: str) -> Tuple[ParsedStatement, bool]:
        logger.info(f"Worker thread starting job for hash: {file_hash}")
        
        pdf_pages = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                words = page.extract_words()
                pdf_pages.append({"text": text, "words": words})
                
        return self.orchestrator.process_document(pdf_pages, file_hash)
import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
sys.path.insert(0, src_dir)

from parser_app.artifact_repository import ArtifactRepository  # noqa: E402
from parser_app.gemini_client import GeminiLLMClient  # noqa: E402
from parser_app.llm_client import MockLLMClient  # noqa: E402
from parser_app.orchestrator import LearningOrchestrator  # noqa: E402
from parser_app.queue_worker import StatementProcessor  # noqa: E402
from parser_app.statement_repository import StatementRepository  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ActivvParser")

def main():
    parser = argparse.ArgumentParser(description="Activv Money - Self-Learning PMS/AIF Parser")
    parser.add_argument("--input", "-i", type=str, default="tests/fixtures/raw_pdfs", help="Directory containing PDF statements")
    parser.add_argument("--mock", action="store_true", help="Force mock LLM (Offline mode)")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚀 ACTIVV MONEY: SELF-LEARNING PARSER PIPELINE 🚀")
    print("="*60)
    
    start_time = time.time()
    
    repo = ArtifactRepository(db_path="data/artifacts.db")
    stmt_repo = StatementRepository(db_path="data/statements.db")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if args.mock or not api_key or api_key == "your_real_api_key_here":
        logger.warning("No valid GEMINI_API_KEY found or --mock flag used. Falling back to MockLLMClient (Offline Mode).")
        dummy_json = '{"artifact_version": "1.0", "layout_fingerprint": "mock", "provider_name": "MockProvider", "context_rules": [], "summary_rules": [], "holdings_table": null}'
        llm = MockLLMClient(simulate_mode="success", mock_json_response=dummy_json)
    else:
        logger.info("Live Gemini 3.8 Flash Client Initialized.")
        llm = GeminiLLMClient()
        
    orchestrator = LearningOrchestrator(repo, llm)
    processor = StatementProcessor(orchestrator, max_workers=4)

    input_dir = Path(args.input)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    staged_files = []
    for pdf_path in input_dir.glob("*.pdf"):
        file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        staged_files.append((file_hash, str(pdf_path)))
        
    if not staged_files:
        logger.warning(f"No PDFs found in {input_dir}")
        sys.exit(0)

    logger.info(f"Queueing {len(staged_files)} documents for parallel processing...\n")
    
    results = []
    try:
        results = processor.process_batch(staged_files)
        for stmt in results:
            stmt_repo.save_statement(stmt)
    except KeyboardInterrupt:
        print("\n\n🛑 SHUTDOWN SIGNAL RECEIVED (Ctrl+C) 🛑")
        print("Gracefully halting workers and preventing database corruption...")
        sys.exit(130)

    # Calculate Metrics
    elapsed_time = time.time() - start_time
    total_docs = len(staged_files)
    successful_docs = len([s for s in results if s.validation.status.name == "PASS"])
    failed_docs = total_docs - successful_docs
    throughput = total_docs / elapsed_time if elapsed_time > 0 else 0

    print("\n" + "="*60)
    print("📊 OBSERVABILITY & PERFORMANCE METRICS 📊")
    print("="*60)
    print(f"Total Time:      {elapsed_time:.2f} seconds")
    print(f"Throughput:      {throughput:.2f} documents/second")
    print(f"Success Rate:    {successful_docs}/{total_docs} ({(successful_docs/total_docs)*100 if total_docs else 0:.1f}%)")
    print(f"Quarantined:     {failed_docs} (Requires Human Review)")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
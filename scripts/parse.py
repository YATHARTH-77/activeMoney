import os
import argparse
import logging
from pathlib import Path
import hashlib
from dotenv import load_dotenv

from parser_app.artifact_repository import ArtifactRepository
from parser_app.statement_repository import StatementRepository
from parser_app.orchestrator import LearningOrchestrator
from parser_app.queue_worker import StatementProcessor
from parser_app.llm_client import MockLLMClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Pipeline")

def main():
    parser = argparse.ArgumentParser(description="Activv Money Parser Pipeline")
    parser.add_argument("--input", default="tests/fixtures/raw_pdfs", help="Directory containing PDFs")
    parser.add_argument("--workers", type=int, default=1, help="Max parallel workers (Set to 1 to respect Groq free-tier rate limits)")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚀 ACTIVV MONEY: MULTI-PROVIDER AI PIPELINE 🚀")
    print("="*60)

    repo = ArtifactRepository(db_path="data/artifacts.db")
    stmt_repo = StatementRepository(db_path="data/statements.db")

    # BUILD THE LLM ROUTING POOL
    llm_clients = []
    
    groq_key = os.getenv("GROQ_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if groq_key and groq_key != "your_groq_api_key_here":
        from parser_app.groq_client import GroqLLMClient
        logger.info("🟢 Added Groq (gpt-oss-20b) to routing pool as Primary.")
        llm_clients.append(GroqLLMClient())
        
    if gemini_key and gemini_key != "your_real_api_key_here":
        from parser_app.gemini_client import GeminiLLMClient
        logger.info("🔵 Added Gemini (3.8-flash) to routing pool as Fallback.")
        llm_clients.append(GeminiLLMClient())

    if not llm_clients:
        logger.warning("No API keys found. Falling back to MockLLMClient.")
        dummy_json = '{"artifact_version": "1.0", "layout_fingerprint": "mock", "provider_name": "MockProvider", "context_rules": [], "summary_rules": [], "holdings_table": null}'
        llm_clients.append(MockLLMClient(simulate_mode="success", mock_json_response=dummy_json))

    orchestrator = LearningOrchestrator(repo, llm_clients)
    
    # We set max_workers=1 by default to prevent Groq from throwing 429 Rate Limit errors
    processor = StatementProcessor(orchestrator, max_workers=args.workers)

    input_dir = Path(args.input)
    if not input_dir.exists():
        logger.error(f"Input directory {input_dir} not found.")
        return

    staged_files = []
    for pdf_path in input_dir.glob("*.pdf"):
        file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        staged_files.append((file_hash, str(pdf_path)))

    if not staged_files:
        logger.info(f"No PDFs found in {input_dir}.")
        return

    logger.info(f"Queueing {len(staged_files)} documents for processing...\n")
    
    results = processor.process_batch(staged_files)
    
    success_count = 0
    for stmt in results:
        stmt_repo.save_statement(stmt)
        if stmt.validation.status.name == "PASS":
            success_count += 1

    print("\n" + "="*60)
    print("📊 OBSERVABILITY & PERFORMANCE METRICS 📊")
    print("="*60)
    if processor.metrics.total_processing_time > 0:
        throughput = len(results) / processor.metrics.total_processing_time
    else:
        throughput = 0.0
        
    print(f"Total Time:      {processor.metrics.total_processing_time:.2f} seconds")
    print(f"Throughput:      {throughput:.2f} documents/second")
    print(f"Success Rate:    {success_count}/{len(results)} ({(success_count/len(results))*100:.1f}%)")
    print(f"Quarantined:     {len(results) - success_count} (Requires Human Review)")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
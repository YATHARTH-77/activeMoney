import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path

# Dynamically add the 'src' directory to Python's path so it can find 'parser_app'
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
sys.path.insert(0, src_dir)

from parser_app.artifact_repository import ArtifactRepository  # noqa: E402
from parser_app.gemini_client import GeminiLLMClient  # noqa: E402
from parser_app.llm_client import MockLLMClient  # noqa: E402
from parser_app.orchestrator import LearningOrchestrator  # noqa: E402
from parser_app.queue_worker import StatementProcessor  # noqa: E402
from parser_app.statement_repository import StatementRepository  # noqa: E402

# Set up clean terminal logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ActivvParser")

def main():
    parser = argparse.ArgumentParser(description="Activv Money - Self-Learning PMS/AIF Parser")
    parser.add_argument(
        "--input", "-i", type=str, default="tests/fixtures/raw_pdfs", 
        help="Directory containing PDF statements to process"
    )
    parser.add_argument(
        "--mock", action="store_true", 
        help="Force mock LLM (Offline mode, no API calls)"
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚀 ACTIVV MONEY: SELF-LEARNING PARSER PIPELINE 🚀")
    print("="*60)
    
    # 1. Initialize Database
    repo = ArtifactRepository(db_path="data/artifacts.db")
    stmt_repo = StatementRepository(db_path="data/statements.db")
    
    # 2. Smart LLM Initialization (Reviewer-friendly failover)
    api_key = os.getenv("GEMINI_API_KEY")
    if args.mock or not api_key or api_key == "your_real_api_key_here":
        logger.warning("No valid GEMINI_API_KEY found or --mock flag used.")
        logger.info("Falling back to MockLLMClient (Offline Mode).")
        dummy_json = '{"artifact_version": "1.0", "layout_fingerprint": "mock", "provider_name": "MockProvider", "context_rules": [], "summary_rules": [], "holdings_table": null}'
        llm = MockLLMClient(simulate_mode="success", mock_json_response=dummy_json)
    else:
        logger.info("Live Gemini 3.8 Flash Client Initialized.")
        llm = GeminiLLMClient()
        
    # 3. Initialize Core Logic
    orchestrator = LearningOrchestrator(repo, llm)
    processor = StatementProcessor(orchestrator, max_workers=4)

    input_dir = Path(args.input)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    # 4. Simulate Ingestion (Hash & Stage)
    staged_files = []
    for pdf_path in input_dir.glob("*.pdf"):
        file_bytes = pdf_path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        staged_files.append((file_hash, str(pdf_path)))
        
    if not staged_files:
        logger.warning(f"No PDFs found in {input_dir}")
        sys.exit(0)

    logger.info(f"Queueing {len(staged_files)} documents for parallel processing...\n")
    
    # 5. Execute Pipeline!
    results = processor.process_batch(staged_files)
    
    for stmt in results:
        stmt_repo.save_statement(stmt)

    # 6. Output Final Results
    print("\n" + "="*60)
    print("🎉 PIPELINE EXECUTION COMPLETE 🎉")
    print("="*60)
    
    for stmt in results:
        status_color = "✅" if stmt.validation.status.name == "PASS" else "❌"
        print(f"\n{status_color} Statement Hash: {stmt.provenance.source_hash[:8]}...")
        print(f"   Provider: {stmt.context.provider_name}")
        print(f"   Status:   {stmt.validation.status.name}")
        print(f"   Details:  {stmt.validation.details}")
        print(f"   Holdings: {len(stmt.holdings)} assets extracted")
        print("   JSON Output Snippet:")
        print(f"   {stmt.model_dump_json(indent=2)[:400]}...\n")

if __name__ == "__main__":
    main()
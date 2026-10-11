import argparse
import os
import sys

# Dynamically add the 'src' directory to Python's path so it can find 'parser_app'
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
sys.path.insert(0, src_dir)

# Tell Ruff to ignore the E402 (import not at top) rule for this specific line
from parser_app.extractor import PDFExtractionError, PDFExtractor  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostic tool to inspect PDF coordinate boundaries."
    )
    parser.add_argument("file_path", help="Path to the PDF file")
    parser.add_argument("--limit", type=int, default=20, help="Number of words to show per page")
    
    args = parser.parse_args()
    
    try:
        pages = PDFExtractor.extract_page_data(args.file_path)
        for page in pages:
            print(f"\n--- Page {page['page_number']} [Size: {page['width']}x{page['height']}] ---")
            print("First few words and coordinates (x0, top, x1, bottom):")
            for i, word in enumerate(page['words'][:args.limit]):
                coords = (
                    f"({word['x0']:.2f}, {word['top']:.2f}, "
                    f"{word['x1']:.2f}, {word['bottom']:.2f})"
                )
                print(f"  {coords:^40} | '{word['text']}'")
            
            if len(page['words']) > args.limit:
                print(f"  ... and {len(page['words']) - args.limit} more words.")
                
    except PDFExtractionError as e:
        print(f"Extraction Error: {e}", file=sys.stderr)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)


if __name__ == "__main__":
    main()
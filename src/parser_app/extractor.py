import os
from typing import Any, Dict, List, Tuple

import pdfplumber


class PDFExtractionError(Exception):
    """Base exception for PDF extraction issues."""
    pass


class PDFExtractor:
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
    MAX_PAGES = 50

    @classmethod
    def extract_page_data(cls, file_path: str) -> List[Dict[str, Any]]:
        """Safely extracts text and exact word coordinates from a PDF."""
        cls._validate_file(file_path)

        pages_data = []
        try:
            with pdfplumber.open(file_path) as pdf:
                if len(pdf.pages) > cls.MAX_PAGES:
                    raise PDFExtractionError(
                        f"PDF exceeds maximum page limit of {cls.MAX_PAGES}."
                    )

                for page_num, page in enumerate(pdf.pages):
                    words = page.extract_words(keep_blank_chars=False)
                    text = page.extract_text() or ""

                    if not text.strip() and not words:
                        raise PDFExtractionError(
                            f"Page {page_num + 1} has no text layers. "
                            "This may be a scanned document."
                        )

                    pages_data.append({
                        "page_number": page_num + 1,
                        "width": page.width,
                        "height": page.height,
                        "text": text,
                        "words": words
                    })
            return pages_data
        except Exception as e:
            if "Password" in str(e) or "password" in str(e).lower():
                raise PDFExtractionError("PDF is password protected. Manual review required.")
            elif isinstance(e, PDFExtractionError):
                raise
            else:
                raise PDFExtractionError(f"Failed to process PDF: {str(e)}")

    @classmethod
    def extract_region(
        cls, file_path: str, page_num: int, bbox: Tuple[float, float, float, float]
    ) -> str:
        """
        Extracts text from a specific geometric region (x0, top, x1, bottom).
        Useful for targeted deterministic extraction.
        """
        cls._validate_file(file_path)
        try:
            with pdfplumber.open(file_path) as pdf:
                page = pdf.pages[page_num - 1]
                cropped = page.within_bbox(bbox)
                return cropped.extract_text() or ""
        except Exception as e:
            raise PDFExtractionError(f"Failed to extract region: {str(e)}")

    @classmethod
    def _validate_file(cls, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size > cls.MAX_FILE_SIZE_BYTES:
            raise PDFExtractionError(
                f"File size ({file_size} bytes) exceeds limit of {cls.MAX_FILE_SIZE_BYTES} bytes."
            )
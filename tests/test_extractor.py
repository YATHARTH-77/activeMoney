import os

import pytest
from reportlab.pdfgen import canvas

from parser_app.extractor import PDFExtractionError, PDFExtractor

# Setup paths based on Phase 4 fixtures
VALID_PDF = "tests/fixtures/raw_pdfs/alpha_wealth.pdf"
EMPTY_PDF = "tests/fixtures/raw_pdfs/empty_scanned.pdf"

@pytest.fixture(autouse=True)
def setup_empty_pdf():
    """Create a completely blank PDF on the fly to simulate a scanned/image-only document."""
    c = canvas.Canvas(EMPTY_PDF)
    # Drawing nothing acts like a scanned PDF with no text layers
    c.showPage()
    c.save()
    yield
    # Cleanup after tests
    if os.path.exists(EMPTY_PDF):
        os.remove(EMPTY_PDF)


def test_successful_extraction():
    """Verify we can extract words and coordinates from a valid PDF."""
    data = PDFExtractor.extract_page_data(VALID_PDF)
    assert len(data) > 0
    assert "page_number" in data[0]
    assert "words" in data[0]
    
    # Check that coordinate dictionaries are formed correctly
    first_word = data[0]["words"][0]
    assert "x0" in first_word
    assert "top" in first_word
    assert "text" in first_word


def test_scanned_or_empty_pdf_raises_error():
    """Verify that a PDF with no text layers safely raises an exception."""
    with pytest.raises(PDFExtractionError) as exc_info:
        PDFExtractor.extract_page_data(EMPTY_PDF)
    assert "no text layers" in str(exc_info.value).lower()


def test_file_size_limit(monkeypatch):
    """Verify that files exceeding the configured byte limit are rejected."""
    # Temporarily set max size to 10 bytes to force a failure
    monkeypatch.setattr(PDFExtractor, "MAX_FILE_SIZE_BYTES", 10)
    with pytest.raises(PDFExtractionError) as exc_info:
        PDFExtractor.extract_page_data(VALID_PDF)
    assert "exceeds limit" in str(exc_info.value).lower()


def test_region_extraction():
    """Verify we can crop and extract a specific coordinate bounding box."""
    # Alpha wealth PDF has the word "AlphaWealth" near the top left
    # Bbox: x0=0, top=0, x1=300, bottom=100
    text = PDFExtractor.extract_region(VALID_PDF, page_num=1, bbox=(0, 0, 300, 100))
    assert "AlphaWealth" in text
import pytest

from parser_app.extractor import PDFExtractor
from parser_app.fingerprinter import FingerprintMatch, LayoutFingerprinter, LayoutSignature

VALID_ALPHA_PDF = "tests/fixtures/raw_pdfs/alpha_wealth.pdf"
VALID_BETA_PDF = "tests/fixtures/raw_pdfs/beta_aif.pdf"

@pytest.fixture
def alpha_pages():
    return PDFExtractor.extract_page_data(VALID_ALPHA_PDF)

@pytest.fixture
def beta_pages():
    return PDFExtractor.extract_page_data(VALID_BETA_PDF)

def test_signature_removes_volatile_data(alpha_pages):
    """Verify that numbers (like 2026, 1000000) are entirely stripped from the signature."""
    sig = LayoutFingerprinter.observe(alpha_pages)
    
    # Check that known boilerplate survived
    assert "alphawealth" in sig.structural_text
    assert "portfolio" in sig.structural_text
    assert "summary" in sig.structural_text
    
    # Check that volatile data was destroyed
    assert "2026" not in sig.structural_text
    assert "1000000" not in sig.structural_text
    assert "a01" not in sig.structural_text # CLIENT-A01 had a digit, so it was dropped

def test_exact_match(alpha_pages):
    """Parsing the identical layout twice should yield a MATCH."""
    sig1 = LayoutFingerprinter.observe(alpha_pages)
    sig2 = LayoutFingerprinter.observe(alpha_pages)
    
    assert LayoutFingerprinter.compare(sig1, sig2) == FingerprintMatch.MATCH

def test_completely_different_formats(alpha_pages, beta_pages):
    """AlphaWealth and Beta AIF have different text. They should return OBSERVATION_FAILED."""
    alpha_sig = LayoutFingerprinter.observe(alpha_pages)
    beta_sig = LayoutFingerprinter.observe(beta_pages)
    
    result = LayoutFingerprinter.compare(alpha_sig, beta_sig)
    assert result == FingerprintMatch.OBSERVATION_FAILED

def test_layout_drift_detection():
    """Simulate a provider quietly adding a new column header."""
    active_sig = LayoutSignature(
        page_count=1,
        structural_text="account summary holdings security name isin quantity market value",
        fingerprint_hash="fake1"
    )
    
    # The provider added "unrealized gain" to the template
    drifted_sig = LayoutSignature(
        page_count=1,
        structural_text="account summary holdings security name isin quantity unrealized gain market value",
        fingerprint_hash="fake2"
    )
    
    result = LayoutFingerprinter.compare(drifted_sig, active_sig)
    
    # It shares most words, but isn't exact. It should flag as DRIFT.
    assert result == FingerprintMatch.DRIFT
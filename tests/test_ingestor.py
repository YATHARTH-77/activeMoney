import os
from email.message import EmailMessage
from pathlib import Path

import pytest

from parser_app.ingestor import EmailIngestor


@pytest.fixture
def temp_staging(tmp_path):
    """Provides an isolated staging directory for tests."""
    staging_dir = tmp_path / "staging"
    return EmailIngestor(staging_dir=str(staging_dir))

@pytest.fixture
def synthetic_email_bytes():
    """Builds a multipart email in memory with a PDF and a PNG attachment."""
    msg = EmailMessage()
    msg['Subject'] = 'Your Monthly Portfolio Statement'
    msg['From'] = 'reports@alphawealth.com'
    msg['To'] = 'client@activvmoney.com'
    msg.set_content('Please find your statement attached.')

    # 1. Attach a fake PDF (just binary data)
    fake_pdf_data = b"%PDF-1.4 fake pdf binary data"
    msg.add_attachment(
        fake_pdf_data, 
        maintype='application', 
        subtype='pdf', 
        filename='statement_october.pdf'
    )

    # 2. Attach a fake PNG (e.g., a signature logo - should be ignored)
    fake_png_data = b"\x89PNG\r\n\x1a\n fake image data"
    msg.add_attachment(
        fake_png_data, 
        maintype='image', 
        subtype='png', 
        filename='logo.png'
    )
    
    return msg.as_bytes()

def test_extract_only_pdfs(temp_staging, synthetic_email_bytes):
    """The ingestor must extract the PDF and completely ignore the PNG."""
    results = temp_staging.process_eml_bytes(synthetic_email_bytes)
    
    # It should only return 1 item (the PDF)
    assert len(results) == 1
    
    file_hash, file_path = results[0]
    
    # Ensure the file was actually written to disk
    assert os.path.exists(file_path)
    assert file_path.endswith(".pdf")
    
    # Ensure the hash is deterministic
    import hashlib
    expected_hash = hashlib.sha256(b"%PDF-1.4 fake pdf binary data").hexdigest()
    assert file_hash == expected_hash

def test_idempotency_duplicate_handling(temp_staging, synthetic_email_bytes):
    """Processing the exact same email twice shouldn't crash or duplicate files."""
    # First pass
    results1 = temp_staging.process_eml_bytes(synthetic_email_bytes)
    
    # Second pass
    results2 = temp_staging.process_eml_bytes(synthetic_email_bytes)
    
    assert len(results1) == 1
    assert len(results2) == 1
    
    # Both passes should return the exact same hash and filepath
    assert results1[0][0] == results2[0][0]
    
    # Verify there is still only exactly 1 file in the staging directory
    staged_files = list(Path(temp_staging.staging_dir).iterdir())
    assert len(staged_files) == 1
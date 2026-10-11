import email
import hashlib
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

class EmailIngestor:
    def __init__(self, staging_dir: str = "data/staging"):
        self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def process_eml_bytes(self, eml_bytes: bytes) -> List[Tuple[str, str]]:
        """
        Parses raw email bytes, extracts PDF attachments, hashes them, 
        and saves them to the staging directory.
        
        Returns:
            List of Tuples containing (source_hash, saved_file_path)
        """
        msg = email.message_from_bytes(eml_bytes)
        extracted_pdfs = []

        # Walk through the email parts (Body, HTML, Attachments)
        for part in msg.walk():
            # Skip container parts
            if part.get_content_maintype() == "multipart":
                continue
                
            filename = part.get_filename()
            if not filename:
                continue
                
            # Security & Scope constraint: Only process PDFs
            if not filename.lower().endswith(".pdf"):
                logger.debug(f"Ignoring non-PDF attachment: {filename}")
                continue

            # Safely decode the base64 attachment payload
            payload = part.get_payload(decode=True)
            if not payload:
                continue

            # Calculate SHA-256 for idempotency and provenance
            file_hash = hashlib.sha256(payload).hexdigest()
            
            # Save the file using its hash as the filename to prevent overwrites
            # and guarantee we know exactly what this file is.
            safe_filename = f"{file_hash}.pdf"
            out_path = self.staging_dir / safe_filename
            
            if not out_path.exists():
                out_path.write_bytes(payload)
                logger.info(f"Extracted and staged: {safe_filename} (from {filename})")
            else:
                logger.info(f"Duplicate detected, skipping staging: {safe_filename}")

            extracted_pdfs.append((file_hash, str(out_path)))

        return extracted_pdfs
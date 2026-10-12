import imaplib
import logging
import os
import sys

from dotenv import load_dotenv

from parser_app.ingestor import EmailIngestor

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
sys.path.insert(0, src_dir)


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("GmailCollector")

def collect_unread_emails():
    # Setup your dummy Gmail and App Password in the .env file
    email_user = os.getenv("GMAIL_USER")
    email_pass = os.getenv("GMAIL_APP_PASSWORD")
    
    if not email_user or not email_pass:
        logger.error("GMAIL_USER or GMAIL_APP_PASSWORD missing in .env")
        logger.info("Please generate an App Password from your Google Account Security settings.")
        return

    logger.info(f"Connecting to imap.gmail.com as {email_user}...")
    
    try:
        # Connect to Gmail IMAP securely
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_user, email_pass)
        mail.select("inbox")
        
        # Search for UNSEEN (unread) emails
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()
        
        if not email_ids:
            logger.info("No new unread statements found in the inbox.")
            return

        logger.info(f"Found {len(email_ids)} unread emails. Processing...")
        
        ingestor = EmailIngestor(staging_dir="data/staging")
        
        for e_id in email_ids:
            # Fetch the raw RFC822 email bytes
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    raw_email_bytes = response_part[1]
                    
                    # Pass the bytes directly to our Phase 13 Ingestor!
                    extracted_files = ingestor.process_eml_bytes(raw_email_bytes)
                    
                    for doc_hash, path in extracted_files:
                        logger.info(f"Successfully staged PDF from email: {path}")
                        
        logger.info("Email collection complete. PDFs are ready in data/staging/ for parse.py!")
        mail.logout()
        
    except Exception as e:
        logger.error(f"IMAP Connection failed: {e}")

if __name__ == "__main__":
    collect_unread_emails()
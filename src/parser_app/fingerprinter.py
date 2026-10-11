import hashlib
import re
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel


class FingerprintMatch(str, Enum):
    MATCH = "MATCH"
    REVIEW = "REVIEW"
    DRIFT = "DRIFT"
    OBSERVATION_FAILED = "OBSERVATION_FAILED"

class LayoutSignature(BaseModel):
    page_count: int
    structural_text: str
    fingerprint_hash: str

class LayoutFingerprinter:
    @classmethod
    def observe(cls, pages_data: List[Dict[str, Any]]) -> LayoutSignature:
        """
        Distills raw extracted PDF pages into a stable structural signature 
        by removing volatile data like numbers, dates, and client IDs.
        """
        if not pages_data:
            raise ValueError("No pages data provided to observer.")
        
        # We base the structural fingerprint primarily on the first page.
        # This guarantees speed and stability, as page 1 contains the headers/templates.
        first_page = pages_data[0]
        words = first_page.get("words", [])
        
        cleaned_words = []
        for w in words:
            text = w["text"].lower()
            
            # 1. Volatile filter: If the word contains ANY digit, drop it entirely.
            # This instantly removes dates (2026), amounts (1000.00), and IDs (CLIENT-A01).
            if re.search(r'\d', text):
                continue
                
            # 2. Clean punctuation from the remaining boilerplate
            cleaned_text = re.sub(r'[^a-z]', '', text)
            
            # 3. Ignore tiny noise artifacts (like "rs", "a", "of")
            if len(cleaned_text) > 2: 
                cleaned_words.append(cleaned_text)
                
        structural_text = " ".join(cleaned_words)
        
        # Create a deterministic SHA-256 hash of the resulting boilerplate template
        f_hash = hashlib.sha256(structural_text.encode("utf-8")).hexdigest()
        
        return LayoutSignature(
            page_count=len(pages_data),
            structural_text=structural_text,
            fingerprint_hash=f_hash
        )

    @classmethod
    def compare(cls, candidate: LayoutSignature, active: LayoutSignature) -> FingerprintMatch:
        """
        Compares an incoming statement's signature against a known active artifact's signature.
        """
        if candidate.fingerprint_hash == active.fingerprint_hash:
            return FingerprintMatch.MATCH
            
        # If the exact hash fails, calculate Jaccard Similarity (Intersection over Union)
        # to determine if it is a slight layout drift or a completely different provider.
        set1 = set(candidate.structural_text.split())
        set2 = set(active.structural_text.split())
        
        if not set1 or not set2:
            return FingerprintMatch.OBSERVATION_FAILED
            
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        similarity = intersection / union
        
        if similarity > 0.95:
            # Hash failed, but text is 95% identical (e.g., a tiny typo fix by the provider)
            return FingerprintMatch.REVIEW
        elif similarity > 0.70:
            # High overlap, but clear structural changes (e.g., they added a new column)
            return FingerprintMatch.DRIFT
        else:
            # Completely different format (e.g., AlphaWealth vs Beta AIF)
            return FingerprintMatch.OBSERVATION_FAILED
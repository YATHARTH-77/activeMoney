import sqlite3
from enum import Enum
from typing import List, Optional

from parser_app.artifact_schema import LayoutArtifact


class ArtifactStatus(Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"

class ArtifactRepository:
    def __init__(self, db_path: str = "data/artifacts.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT UNIQUE NOT NULL,
                    provider_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    json_payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_candidate(self, artifact: LayoutArtifact) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO artifacts (fingerprint, provider_name, status, json_payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    status=excluded.status,
                    json_payload=excluded.json_payload
            """, (
                artifact.layout_fingerprint,
                artifact.provider_name,
                ArtifactStatus.CANDIDATE.value,
                artifact.model_dump_json()
            ))
            conn.commit()
            return cursor.lastrowid

    def get_active_artifact(self, fingerprint: str) -> Optional[LayoutArtifact]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT json_payload FROM artifacts 
                WHERE fingerprint = ? AND status = ?
            """, (fingerprint, ArtifactStatus.ACTIVE.value))
            row = cursor.fetchone()
            if row:
                return LayoutArtifact.model_validate_json(row[0])
            return None

    # NEW: Used to check existing providers for drift detection
    def get_all_active_artifacts(self) -> List[LayoutArtifact]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_payload FROM artifacts WHERE status = ?", (ArtifactStatus.ACTIVE.value,))
            return [LayoutArtifact.model_validate_json(row[0]) for row in cursor.fetchall()]

    # UPDATED: Safely deprecate old layouts from the same provider when a drift is validated
    def promote_to_active(self, artifact_id: int, provider_name: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Step 1: Deprecate any currently active artifact for this specific provider
            cursor.execute("""
                UPDATE artifacts SET status = ?
                WHERE provider_name = ? AND status = ?
            """, (ArtifactStatus.DEPRECATED.value, provider_name, ArtifactStatus.ACTIVE.value))
            
            # Step 2: Promote the new candidate
            cursor.execute("""
                UPDATE artifacts SET status = ?
                WHERE id = ?
            """, (ArtifactStatus.ACTIVE.value, artifact_id))
            conn.commit()
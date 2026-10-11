import sqlite3
from enum import Enum
from typing import Optional

from parser_app.artifact_schema import LayoutArtifact


class ArtifactStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    REJECTED = "REJECTED"

class ArtifactRepository:
    def __init__(self, db_path: str = "data/artifacts.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Creates the tables and the strict partial unique index."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # The Magic Sauce: Enforce only one ACTIVE artifact per layout fingerprint
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_per_fingerprint 
                ON artifacts(fingerprint) WHERE status = 'ACTIVE'
            """)
            conn.commit()

    def save_candidate(self, artifact: LayoutArtifact) -> int:
        """Saves a newly generated LLM artifact in a safe CANDIDATE state."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO artifacts (fingerprint, version, status, artifact_json)
                VALUES (?, ?, ?, ?)
            """, (
                artifact.layout_fingerprint,
                artifact.artifact_version,
                ArtifactStatus.CANDIDATE.value,
                artifact.model_dump_json()
            ))
            conn.commit()
            return cursor.lastrowid

    def get_active_artifact(self, fingerprint: str) -> Optional[LayoutArtifact]:
        """Fetches the currently approved parsing rules for a given layout."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT artifact_json FROM artifacts 
                WHERE fingerprint = ? AND status = 'ACTIVE'
            """, (fingerprint,))
            row = cursor.fetchone()

            if not row:
                return None
            
            # Pydantic safely resurrects the object from JSON
            return LayoutArtifact.model_validate_json(row[0])

    def promote_to_active(self, artifact_id: int, fingerprint: str) -> None:
        """Atomically deprecates the old active artifact and promotes the new one."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Step 1: Deprecate currently active artifact for this fingerprint
            cursor.execute("""
                UPDATE artifacts SET status = ? 
                WHERE fingerprint = ? AND status = ?
            """, (
                ArtifactStatus.DEPRECATED.value, 
                fingerprint, 
                ArtifactStatus.ACTIVE.value
            ))
            
            # Step 2: Promote the candidate to active
            cursor.execute("""
                UPDATE artifacts SET status = ? 
                WHERE id = ?
            """, (ArtifactStatus.ACTIVE.value, artifact_id))
            
            # Transaction commits both safely
            conn.commit()
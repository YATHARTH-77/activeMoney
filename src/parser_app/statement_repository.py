import sqlite3
from typing import Any, Dict, List, Optional

from parser_app.schema import ParsedStatement


class StatementRepository:
    def __init__(self, db_path: str = "data/statements.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statements (
                    statement_id TEXT PRIMARY KEY,
                    provider_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    artifact_version TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    json_payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_statement(self, statement: ParsedStatement) -> None:
        """Upserts a parsed statement into the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO statements 
                (statement_id, provider_name, status, details, artifact_version, json_payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(statement_id) DO UPDATE SET
                    status=excluded.status,
                    details=excluded.details,
                    json_payload=excluded.json_payload
            """, (
                statement.statement_id,
                statement.context.provider_name,
                statement.validation.status.value,
                statement.validation.details,
                statement.provenance.artifact_version,
                statement.model_dump_json()
            ))
            conn.commit()

    def list_statements(self, status_filter: str = "ALL", limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Fetches a paginated list of statements for the review queue."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT statement_id, provider_name, status, details, resolved, created_at FROM statements"
            params = []
            
            if status_filter != "ALL":
                query += " WHERE status = ?"
                params.append(status_filter)
                
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_statement_json(self, statement_id: str) -> Optional[str]:
        """Fetches the raw JSON payload for detailed review."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_payload FROM statements WHERE statement_id = ?", (statement_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def mark_resolved(self, statement_id: str) -> bool:
        """Marks a quarantined statement as human-reviewed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE statements SET resolved = 1 WHERE statement_id = ?", (statement_id,))
            conn.commit()
            return cursor.rowcount > 0
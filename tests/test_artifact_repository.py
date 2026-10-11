import sqlite3

import pytest

from parser_app.artifact_repository import ArtifactRepository
from parser_app.artifact_schema import LayoutArtifact, TableDefinition


@pytest.fixture
def repo(tmp_path):
    """
    Uses Pytest's built-in tmp_path to create a temporary file-based database.
    This perfectly mimics production behavior and avoids the ':memory:' connection trap.
    """
    # Create a unique temporary file path for this specific test run
    db_file = tmp_path / "test_artifacts.db"
    return ArtifactRepository(db_path=str(db_file))

@pytest.fixture
def sample_artifact():
    return LayoutArtifact(
        artifact_version="1.0",
        layout_fingerprint="alpha_v1",
        provider_name="AlphaWealth",
        context_rules=[],
        summary_rules=[],
        holdings_table=TableDefinition(start_anchor="Holdings", columns=[])
    )

def test_save_and_retrieve_candidate(repo, sample_artifact):
    """Ensure artifacts are saved as CANDIDATE and don't leak into ACTIVE queries."""
    repo.save_candidate(sample_artifact)
    
    # It is a candidate, so getting the ACTIVE artifact should return None
    active = repo.get_active_artifact("alpha_v1")
    assert active is None

def test_promotion_lifecycle(repo, sample_artifact):
    """Ensure a candidate can be promoted to active, and is retrievable."""
    artifact_id = repo.save_candidate(sample_artifact)
    repo.promote_to_active(artifact_id, "alpha_v1")
    
    active = repo.get_active_artifact("alpha_v1")
    assert active is not None
    assert active.provider_name == "AlphaWealth"

def test_strict_one_active_constraint(repo, sample_artifact):
    """Ensure the database rejects attempts to force multiple active artifacts."""
    # Create two different versions of the artifact
    v1_id = repo.save_candidate(sample_artifact)
    
    sample_artifact.artifact_version = "2.0"
    v2_id = repo.save_candidate(sample_artifact)
    
    # Promote v1
    repo.promote_to_active(v1_id, "alpha_v1")
    
    # Bypassing the `promote_to_active` logic to try and force a duplicate ACTIVE state
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        with sqlite3.connect(repo.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE artifacts SET status = 'ACTIVE' WHERE id = ?", (v2_id,)
            )
    
    # The partial unique index must block this!
    assert "UNIQUE constraint failed" in str(exc_info.value)

def test_safe_upgrade(repo, sample_artifact):
    """Ensure our promote method safely deprecates the old before activating the new."""
    v1_id = repo.save_candidate(sample_artifact)
    repo.promote_to_active(v1_id, "alpha_v1")
    
    sample_artifact.artifact_version = "2.0"
    v2_id = repo.save_candidate(sample_artifact)
    
    # Promote v2 (this should deprecate v1 under the hood)
    repo.promote_to_active(v2_id, "alpha_v1")
    
    active = repo.get_active_artifact("alpha_v1")
    assert active.artifact_version == "2.0"
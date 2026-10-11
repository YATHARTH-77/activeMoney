"""
Basic health check to ensure the pytest framework and environment are configured correctly.
"""

def test_environment_health():
    """Verify that tests can run and assertions work."""
    assert True

def test_imports():
    """Verify that core dependencies are installed and accessible."""
    import pdfplumber
    import pydantic
    import pytest
    
    assert pydantic is not None
    assert pdfplumber is not None
    assert pytest is not None
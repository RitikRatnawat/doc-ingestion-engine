"""Module for testing the security constraints for the Webpage URLs"""

import pytest
from src.docingest import URLValidator


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "file:///etc/passwd",
        "ftp://example.com/",
    ],
)
def test_blocked_urls(url):
    """Test that blocked URLs raise UnsafeURLError."""

    assert not URLValidator.is_valid_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.google.com/",
        "http://example.com",
        "https://docs.python.org/",
        "https://beautiful-soup-4.readthedocs.io/en/latest/",
    ],
)
def test_allowed_urls(url):
    """Test that allowed URLs are valid."""

    assert URLValidator.is_valid_url(url)

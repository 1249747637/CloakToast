"""
Browser service stubs.
Real implementation comes in Task 3 (Browser Worker + process management).
"""


def is_running(profile_id: str) -> bool:
    """Return True if the browser instance for the given profile is running."""
    return False


def get_running_instances() -> dict:
    """
    Return a dict of currently running browser instances keyed by profile_id.
    Each value is a dict with at least {"started_at": "<ISO datetime string>"}.
    """
    return {}

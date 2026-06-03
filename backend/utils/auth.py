"""Authentication helper
- Provide helper for verifying Firebase ID tokens and protecting endpoints.
"""
from typing import Optional


def verify_token(id_token: str) -> Optional[dict]:
    """Verify Firebase ID token and return user info. Placeholder uses no real verification."""
    # TODO: Use firebase_admin.auth.verify_id_token
    if not id_token:
        return None
    return {"uid": "anonymous"}

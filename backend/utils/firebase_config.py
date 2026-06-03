"""Firebase Admin initialization helper
- Configure Firebase Admin SDK for auth and Firestore/Storage access.
"""

# TODO: Initialize firebase_admin with credentials from .env

from firebase_admin import initialize_app, credentials


def init_firebase(cred_path: str = None):
    """Initialize Firebase Admin; pass path to service account JSON."""
    if cred_path:
        cred = credentials.Certificate(cred_path)
        initialize_app(cred)
    else:
        # Fallback to default application credentials
        initialize_app()

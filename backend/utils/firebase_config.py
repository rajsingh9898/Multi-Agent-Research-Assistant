"""Firebase Admin initialization helpers.

This module centralizes Firebase Admin setup so the backend can safely access
Firestore and Storage from any route or service layer.
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Optional, Dict, Any, List
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, storage

logger = logging.getLogger(__name__)

# --- MOCK FIREBASE CLIENTS ---

class MockDocument:
    def __init__(self, data=None, exists=True):
        self._data = data or {}
        self.exists = exists
    def to_dict(self):
        return self._data
    def get(self):
        return self

class MockDocRef:
    def __init__(self, doc_id, collection):
        self.id = doc_id
        self.collection = collection
    def set(self, data, merge=False):
        if self.id not in self.collection.db_mock:
            self.collection.db_mock[self.id] = {}
        if merge:
            self.collection.db_mock[self.id].update(data)
        else:
            self.collection.db_mock[self.id] = data
    def update(self, data):
        if self.id not in self.collection.db_mock:
            self.collection.db_mock[self.id] = {}
        self.collection.db_mock[self.id].update(data)
    def delete(self):
        if self.id in self.collection.db_mock:
            del self.collection.db_mock[self.id]
    def get(self):
        data = self.collection.db_mock.get(self.id)
        return MockDocument(data=data, exists=(data is not None))

class MockStreamDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
    def to_dict(self):
        return self._data

class MockCollection:
    def __init__(self):
        self.db_mock = {}
    def document(self, doc_id):
        return MockDocRef(doc_id, self)
    def where(self, field, op, val):
        return self
    def order_by(self, field, direction=None):
        return self
    def limit(self, lim):
        return self
    def stream(self):
        return [MockStreamDoc(k, v) for k, v in self.db_mock.items()]
    def get(self):
        return [MockStreamDoc(k, v) for k, v in self.db_mock.items()]

class MockFirestoreClient:
    def __init__(self):
        self.collections = {}
    def collection(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection()
        return self.collections[name]

_MOCK_FIRESTORE = MockFirestoreClient()

class MockBlob:
    def __init__(self, name):
        self.name = name
    def upload_from_string(self, data, content_type=None):
        pass
    def make_public(self):
        pass
    @property
    def public_url(self):
        return f"https://storage.googleapis.com/mock-bucket/{self.name}"

class MockBucket:
    def blob(self, name):
        return MockBlob(name)

_MOCK_STORAGE = MockBucket()

# --- HELPER FUNCTIONS ---

def _get_firebase_private_key() -> str:
    """
    Gets Firebase private key from environment.
    Handles multiple formats:
    1. Already has real newlines (from .env file)
    2. Has escaped \\n (from container env var)
    3. Wrapped in quotes (from some CLI tools)
    """
    key = os.getenv("FIREBASE_PRIVATE_KEY", "")
    
    if not key:
        raise ValueError(
            "FIREBASE_PRIVATE_KEY not set. Check your environment variables."
        )
    
    # Remove surrounding quotes if present
    if (key.startswith('"') and key.endswith('"')) or \
       (key.startswith("'") and key.endswith("'")):
        key = key[1:-1]
    
    # Replace escaped newlines with real newlines
    if "\\n" in key:
        key = key.replace("\\n", "\n")
    
    # Validate the key format
    if not key.strip().startswith("-----BEGIN"):
        raise ValueError(
            "FIREBASE_PRIVATE_KEY doesn't look valid. "
            f"Starts with: '{key[:30]}...'"
        )
    
    return key


def _has_service_account_file() -> bool:
    """Check if the service account JSON file actually exists."""
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if not cred_path:
        return False
    path = Path(cred_path)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[1] / path).resolve()
    return path.exists()


def _has_service_account() -> bool:
    """Determine if a valid Firebase configuration or JSON file is configured."""
    if os.getenv("FIREBASE_SERVICE_ACCOUNT"):
        return _has_service_account_file()
    
    # Otherwise check if environment variable config exists (Docker flow)
    return bool(
        os.getenv("FIREBASE_PROJECT_ID") and
        os.getenv("FIREBASE_PRIVATE_KEY") and
        os.getenv("FIREBASE_CLIENT_EMAIL")
    )


def _get_service_account_path() -> str:
    """Return the configured Firebase service account path or raise a clear error."""
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if not cred_path:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT is missing. Set it to the Firebase service account JSON path."
        )

    path = Path(cred_path)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[1] / path).resolve()

    if not path.exists():
        raise RuntimeError(f"Firebase service account file not found: {path}")
    return str(path)


@lru_cache(maxsize=1)
def initialize_firebase() -> Optional[firebase_admin.App]:
    """Initialize Firebase Admin exactly once and return the active app, or Mock App if missing."""
    if not _has_service_account():
        logger.warning("Firebase service account configuration not found. Operating in MOCK mode.")
        print("⚠️  Firebase service account configuration not found. Operating in MOCK mode.")
        return None

    try:
        if firebase_admin._apps:
            return firebase_admin.get_app()

        # Try to initialize using service account file if provided and present
        if os.getenv("FIREBASE_SERVICE_ACCOUNT") and _has_service_account_file():
            cred_path = _get_service_account_path()
            cred = credentials.Certificate(cred_path)
        else:
            # Fallback to loading from individual environment variables (Docker flow)
            cred_dict = {
                "type": "service_account",
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key": _get_firebase_private_key(),
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "token_uri": "https://oauth2.googleapis.com/token"
            }
            cred = credentials.Certificate(cred_dict)

        project_id = os.getenv("FIREBASE_PROJECT_ID")
        app = firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
        logger.info("Firebase Admin initialized successfully")
        return app
    except Exception as exc:
        logger.exception("Failed to initialize Firebase Admin")
        raise RuntimeError(f"Firebase Admin initialization failed: {exc}") from exc


def get_firestore():
    """Return a Firestore client, initializing Firebase if needed. Falls back to mock client."""
    if not _has_service_account():
        return _MOCK_FIRESTORE
    initialize_firebase()
    return firestore.client()


def get_storage():
    """Return a Firebase Storage bucket, initializing Firebase if needed. Falls back to mock client."""
    if not _has_service_account():
        return _MOCK_STORAGE
    initialize_firebase()
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
    if bucket_name:
        return storage.bucket(bucket_name)
    return storage.bucket()


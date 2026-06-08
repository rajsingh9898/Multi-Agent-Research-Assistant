"""Firebase Admin initialization helpers.

This module centralizes Firebase Admin setup so the backend can safely access
Firestore and Storage from any route or service layer.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, storage

logger = logging.getLogger(__name__)


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
def initialize_firebase() -> firebase_admin.App:
    """Initialize Firebase Admin exactly once and return the active app."""
    try:
        if firebase_admin._apps:
            return firebase_admin.get_app()

        cred_path = _get_service_account_path()
        cred = credentials.Certificate(cred_path)
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        app = firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
        logger.info("Firebase Admin initialized successfully")
        return app
    except Exception as exc:
        logger.exception("Failed to initialize Firebase Admin")
        raise RuntimeError(f"Firebase Admin initialization failed: {exc}") from exc


def get_firestore():
    """Return a Firestore client, initializing Firebase if needed."""
    initialize_firebase()
    return firestore.client()


def get_storage():
    """Return a Firebase Storage bucket, initializing Firebase if needed."""
    initialize_firebase()
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
    if bucket_name:
        return storage.bucket(bucket_name)
    return storage.bucket()

"""Authentication helpers for Firebase-backed FastAPI routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import firestore
from firebase_admin.exceptions import FirebaseError

from .firebase_config import get_firestore, initialize_firebase

logger = logging.getLogger(__name__)


def _extract_bearer_token(authorization: Optional[str]) -> str:
    """Extract the raw bearer token from an Authorization header."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
    return token


def verify_token(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """FastAPI dependency that verifies a Firebase ID token and returns the decoded user."""
    try:
        initialize_firebase()
        id_token = _extract_bearer_token(authorization)
        decoded = firebase_auth.verify_id_token(id_token)
        user = {
            "uid": decoded.get("uid"),
            "email": decoded.get("email"),
            "name": decoded.get("name") or decoded.get("firebase", {}).get("sign_in_provider"),
            "picture": decoded.get("picture"),
            "email_verified": decoded.get("email_verified", False),
        }
        return user
    except HTTPException:
        raise
    except firebase_auth.ExpiredIdTokenError as exc:
        logger.warning("Expired Firebase token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except firebase_auth.RevokedIdTokenError as exc:
        logger.warning("Revoked Firebase token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked") from exc
    except firebase_auth.InvalidIdTokenError as exc:
        logger.warning("Invalid Firebase token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    except FirebaseError as exc:
        logger.exception("Firebase auth error")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed") from exc
    except Exception as exc:
        logger.exception("Unexpected authentication error")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed") from exc


def save_user_to_firestore(user: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update the current user document in Firestore."""
    db = get_firestore()
    users_ref = db.collection("users")
    user_id = user["uid"]
    doc_ref = users_ref.document(user_id)
    now = datetime.now(timezone.utc)

    payload = {
        "email": user.get("email"),
        "displayName": user.get("name") or user.get("email") or user_id,
        "photoURL": user.get("picture"),
        "emailVerified": bool(user.get("email_verified", False)),
        "lastLoginAt": firestore.SERVER_TIMESTAMP,
    }

    try:
        snapshot = doc_ref.get()
        if snapshot.exists:
            doc_ref.update(payload)
            logger.info("Updated last login for user %s", user_id)
        else:
            payload["createdAt"] = firestore.SERVER_TIMESTAMP
            payload["totalReports"] = 0
            payload["createdAtClient"] = now.isoformat()
            doc_ref.set(payload)
            logger.info("Created new user document for %s", user_id)
        return {"uid": user_id, **payload}
    except Exception as exc:
        logger.exception("Failed to save user to Firestore")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist user profile") from exc

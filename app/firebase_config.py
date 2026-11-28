"""Firebase Admin SDK initialization and Cloud Firestore client access."""

import json
from pathlib import Path

from flask import current_app
import firebase_admin
from firebase_admin import credentials, firestore

from app.firestore_memory import InMemoryFirestoreClient


BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_credentials_path(raw_path):
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate


def init_firebase(app):
    """Initialize Firestore backend (live Firebase Admin SDK or in-memory test client)."""
    backend = (app.config.get("FIRESTORE_BACKEND") or "firestore").lower()
    if backend == "memory":
        app.extensions["firestore_client"] = InMemoryFirestoreClient()
        return app.extensions["firestore_client"]

    project_id = (app.config.get("FIREBASE_PROJECT_ID") or "").strip()
    cred_path_raw = (app.config.get("FIREBASE_CREDENTIALS_PATH") or "").strip()
    cred_json_raw = (app.config.get("FIREBASE_CREDENTIALS_JSON") or "").strip()

    app_name = f"campus-connect-{project_id or 'default'}"
    try:
        firebase_app = firebase_admin.get_app(app_name)
    except ValueError:
        cred = None
        if cred_json_raw:
            try:
                cred_info = json.loads(cred_json_raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("FIREBASE_CREDENTIALS_JSON is not valid JSON.") from exc
            cred = credentials.Certificate(cred_info)
        elif cred_path_raw:
            cred_path = _resolve_credentials_path(cred_path_raw)
            if not cred_path.exists():
                raise RuntimeError(
                    f"Firebase service account key not found at '{cred_path}'. "
                    "Set FIREBASE_CREDENTIALS_PATH in .env (see FIREBASE_SETUP.md)."
                )
            cred = credentials.Certificate(str(cred_path))
        else:
            raise RuntimeError(
                "Firebase credentials are not configured. Set FIREBASE_CREDENTIALS_PATH "
                "(or FIREBASE_CREDENTIALS_JSON) in .env (see FIREBASE_SETUP.md)."
            )

        options = {"projectId": project_id} if project_id else None
        firebase_app = firebase_admin.initialize_app(cred, options=options, name=app_name)

    client = firestore.client(app=firebase_app)
    app.extensions["firestore_client"] = client
    return client


def get_firestore_client():
    """Return the active Firestore client for the current Flask application."""
    client = current_app.extensions.get("firestore_client")
    if client is None:
        client = init_firebase(current_app)
    return client

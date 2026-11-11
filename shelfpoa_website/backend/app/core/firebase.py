"""
app/core/firebase.py
=====================
Lazy Firebase Realtime Database access for the ShelfPoa backend.

    from app.core.firebase import get_ref
    ref = get_ref("osa_reports")      # firebase_admin.db.Reference, or None

get_ref() returns None -- it never raises -- when Firebase isn't configured, so
routes can fall back to mock data instead of returning a 500. The reason is
logged ONCE to the uvicorn console, not on every request.

Config (backend/.env, which is git-ignored):
    GOOGLE_APPLICATION_CREDENTIALS=C:\\Users\\tednj\\secrets\\firebase-service-account.json
    FIREBASE_DATABASE_URL=https://<project>-default-rtdb.<region>.firebasedatabase.app

If GOOGLE_APPLICATION_CREDENTIALS is unset, falls back to ../secrets/firebase-service-account.json
relative to the backend folder. Relative paths resolve against the backend folder, so it
doesn't matter which directory uvicorn is launched from.
"""

import logging
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

try:  # python-dotenv ships with pydantic-settings; optional here
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/app/core/firebase.py -> backend/
DEFAULT_KEY_PATH = (BACKEND_DIR / ".." / "secrets" / "firebase-service-account.json").resolve()

_log = logging.getLogger("uvicorn.error")  # shows up in the uvicorn console
_state = {"tried": False, "ok": False}


def _init() -> bool:
    """Initialise the Admin SDK once per process. True if usable."""
    if _state["tried"]:
        return _state["ok"]
    _state["tried"] = True

    if load_dotenv is not None:
        load_dotenv(BACKEND_DIR / ".env")  # real environment variables still win

    key_path = Path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or DEFAULT_KEY_PATH)
    if not key_path.is_absolute():
        key_path = (BACKEND_DIR / key_path).resolve()
    db_url = os.getenv("FIREBASE_DATABASE_URL")

    if not key_path.exists():
        _log.warning("Firebase credentials not found at %s - Realtime Database routes will "
                     "fall back to mock data until this is configured.", key_path)
        return False
    if not db_url:
        _log.warning("FIREBASE_DATABASE_URL is not set - Realtime Database routes will "
                     "fall back to mock data.")
        return False

    try:
        try:
            firebase_admin.get_app()  # already initialised (e.g. by another module)
        except ValueError:
            firebase_admin.initialize_app(credentials.Certificate(str(key_path)),
                                          {"databaseURL": db_url})
    except Exception as e:  # unreadable/invalid key file, malformed URL, ...
        _log.warning("Firebase init failed (%s: %s) - Realtime Database routes will "
                     "fall back to mock data.", type(e).__name__, e)
        return False

    _state["ok"] = True
    _log.info("Firebase Realtime Database connected")
    return True


def ready() -> bool:
    """True once the Admin SDK is initialised (needed to verify sign-in tokens)."""
    return _init()


def get_ref(path: str = "/"):
    """Reference for `path`, or None if Firebase isn't configured."""
    if not _init():
        return None
    return db.reference(path)

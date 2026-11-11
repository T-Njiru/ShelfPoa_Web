"""
Central settings. All values are read from environment variables (.env),
so no credentials ever live in source code.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_application_credentials: str = "../secrets/firebase-service-account.json"
    firebase_project_id: str = "planogram-adherance-ver-1"
    # ShelfPoa uses the Firebase Realtime Database (not Firestore).
    # Top-level nodes currently in the DB: audits, mt_groups, osa_reports,
    # outlets_universe, sos_audits.
    firebase_database_url: str = "https://planogram-adherance-ver-1-default-rtdb.firebaseio.com"

    # "mock" -> stubbed responses shaped like real model output
    # "live" -> calls the actual XGBoost / FP-Growth artifacts once trained
    ml_mode: str = "mock"

    frontend_origin: str = "http://localhost:5173"

    # Every /api route except /api/health needs a signed-in admin/manager (app/core/auth.py).
    # false = no check; for local experiments only.
    auth_required: bool = True


settings = Settings()

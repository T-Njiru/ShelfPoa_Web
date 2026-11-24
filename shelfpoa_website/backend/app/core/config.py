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

    # "Continue with Google" is for Flora Food Group accounts, plus any account an admin has
    # already given a role (e.g. an existing admin's own Gmail). Comma-separated email domains;
    # must match VITE_ALLOWED_EMAIL_DOMAINS (web) and AllowedDomains.kt (Android).
    allowed_email_domains: str = "upfield.com,florafoodgroup.com"

    @property
    def allowed_domains(self) -> list[str]:
        return [d.strip().lower().lstrip("@") for d in self.allowed_email_domains.split(",") if d.strip()]

    def email_allowed(self, email: str | None) -> bool:
        domain = (email or "").lower().rpartition("@")[2]
        return bool(domain) and domain in self.allowed_domains


settings = Settings()

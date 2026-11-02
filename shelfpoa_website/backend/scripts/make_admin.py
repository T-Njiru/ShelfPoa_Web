"""
Promote an existing Firebase Auth user to admin.
Run from backend/:  py -m scripts.make_admin you@example.com
"""
import os
import sys
from pathlib import Path

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import auth, credentials, db

# Load backend/.env regardless of where the command is run from
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
db_url = (
    os.getenv("FIREBASE_DATABASE_URL")
    or os.getenv("FIREBASE_DB_URL")
    or os.getenv("DATABASE_URL")
)

if not cred_path:
    sys.exit("GOOGLE_APPLICATION_CREDENTIALS is not set in backend/.env")
if not db_url:
    sys.exit("Database URL not found in backend/.env. Add FIREBASE_DATABASE_URL=https://<project>-default-rtdb.firebaseio.com")

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(cred_path), {"databaseURL": db_url})


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: py -m scripts.make_admin <email>")

    email = sys.argv[1]
    try:
        u = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        sys.exit(f"No Firebase user with email {email}. Create it in Firebase console → Authentication first.")

    auth.set_custom_user_claims(u.uid, {"role": "admin"})
    db.reference(f"users/{u.uid}").set({
        "email": email,
        "display_name": u.display_name or "",
        "role": "admin",
        "active": True,
        "created_at": {".sv": "timestamp"},
    })
    print(f"{email} is now admin (uid {u.uid}). Sign out and back in to refresh the token.")


if __name__ == "__main__":
    main()
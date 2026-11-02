r"""
seed_merchandiser_users.py  --  login accounts for the simulated merchandisers
===============================================================================
Place in backend/ and run from there, AFTER seed_audits.py:

    .\.venv\Scripts\python.exe seed_merchandiser_users.py                              # DRY RUN
    .\.venv\Scripts\python.exe seed_merchandiser_users.py --password <dev-password> --yes
    .\.venv\Scripts\python.exe seed_merchandiser_users.py --purge --yes                # remove them

For each merchandisers/{m-xx} it:
  1. creates a Firebase Auth account  m01@shelfpoa.test  (.test never delivers email)
  2. writes users/{uid}  in the same shape as your admin record, plus merchandiser_id
  3. sets custom claims {role, merchandiser_id} so security rules / the app can read them
  4. writes merchandisers/{m-xx}/uid  so you can go either direction

No report is rewritten: osa_reports / audits / sos_audits already carry merchandiser_id,
so signing in as m01@shelfpoa.test gives you Brian Otieno's visits and readings.
Re-running is safe (existing accounts are reused). --purge deletes only accounts whose
users/{uid}.source == "simulated" -- your admin account is never touched.

Purge order when cleaning up:  this script --purge  ->  seed_audits.py --purge  ->  seed_osa_reports.py --purge
"""

import argparse
import time

EMAIL_DOMAIN = "shelfpoa.test"


def email_for(merch_id: str) -> str:
    return f"{merch_id.replace('-', '')}@{EMAIL_DOMAIN}"  # m-01 -> m01@shelfpoa.test


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", help="dev password for every seeded account (min 6 chars)")
    ap.add_argument("--purge", action="store_true", help="delete simulated merchandiser accounts")
    ap.add_argument("--yes", action="store_true", help="actually write/delete (default is a dry run)")
    args = ap.parse_args()

    from app.core.firebase import get_ref
    users_ref, merch_ref = get_ref("users"), get_ref("merchandisers")
    if users_ref is None or merch_ref is None:
        raise SystemExit("Firebase isn't configured - see the warning above.")
    from firebase_admin import auth  # after get_ref(), which initialises the default app

    if args.purge:
        users = users_ref.get() or {}
        doomed = {uid: u for uid, u in users.items()
                  if isinstance(u, dict) and u.get("source") == "simulated" and u.get("role") == "merchandiser"}
        print(f"{len(doomed)} simulated merchandiser account(s) of {len(users)} users")
        if not args.yes:
            return print("Dry run - re-run with --yes to delete.")
        for uid, u in doomed.items():
            try:
                auth.delete_user(uid)
            except auth.UserNotFoundError:
                pass
            users_ref.child(uid).delete()
            if u.get("merchandiser_id"):
                merch_ref.child(u["merchandiser_id"]).child("uid").delete()
        return print("Deleted.")

    merchandisers = {k: v for k, v in (merch_ref.get() or {}).items() if isinstance(v, dict)}
    if not merchandisers:
        raise SystemExit("merchandisers is empty - run seed_audits.py first.")
    for mid, m in sorted(merchandisers.items()):
        print(f"  {mid:6} {m.get('name', mid):18} -> {email_for(mid)}")
    if not args.yes:
        return print(f"\nDry run - {len(merchandisers)} account(s) would be created. "
                     "Re-run with --password <pw> --yes.")
    if not args.password or len(args.password) < 6:
        raise SystemExit("--password is required with --yes (Firebase needs at least 6 characters).")

    for mid, m in sorted(merchandisers.items()):
        email, name = email_for(mid), m.get("name", mid)
        try:
            user = auth.get_user_by_email(email)
            status = "exists"
        except auth.UserNotFoundError:
            user = auth.create_user(email=email, password=args.password, display_name=name)
            status = "created"
        auth.set_custom_user_claims(user.uid, {"role": "merchandiser", "merchandiser_id": mid})
        existing = users_ref.child(user.uid).get() or {}
        users_ref.child(user.uid).set({
            "active": True,
            "created_at": existing.get("created_at", int(time.time() * 1000)),
            "display_name": name,
            "email": email,
            "role": "merchandiser",
            "merchandiser_id": mid,
            "source": "simulated",
        })
        merch_ref.child(mid).update({"uid": user.uid})
        print(f"  {status:7} {email:22} uid={user.uid}")
    print("Done. Remove later with:  seed_merchandiser_users.py --purge --yes")


if __name__ == "__main__":
    main()

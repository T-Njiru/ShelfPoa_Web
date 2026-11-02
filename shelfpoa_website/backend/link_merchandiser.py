r"""
link_merchandiser.py  --  turn a signed-up account into a merchandiser the dashboard can credit
==================================================================================================
Run from backend\ :

    .\.venv\Scripts\python.exe link_merchandiser.py --email bertrand.omondi@gmail.com             # DRY RUN
    .\.venv\Scripts\python.exe link_merchandiser.py --email bertrand.omondi@gmail.com --name "Bertrand Omondi" --yes

What it does (same as we did by hand for m-09):
  users/{uid}            role = "merchandiser" (an existing "admin"/"manager" role is kept),
                         merchandiser_id = m-NN, active = true, display_name (if --name)
  merchandisers/m-NN     { name, uid }
It also prints how many reports already in Firebase carry that uid -- they are credited
automatically once linked (the backend looks merchandiser_id up from the record's uid).
"""

import argparse
import re
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", help="display name, e.g. 'Bertrand Omondi'")
    ap.add_argument("--id", help="merchandiser id to use (default: next free m-NN)")
    ap.add_argument("--yes", action="store_true", help="actually write (default is a dry run)")
    args = ap.parse_args()

    from app.core.firebase import get_ref
    users_ref, merch_ref = get_ref("users"), get_ref("merchandisers")
    if users_ref is None:
        raise SystemExit("Firebase isn't configured - see the warning above.")
    from firebase_admin import auth

    try:
        user = auth.get_user_by_email(args.email)
    except auth.UserNotFoundError:
        raise SystemExit(f"No Firebase Auth account with email {args.email}")
    uid = user.uid
    record = users_ref.child(uid).get() or {}
    merchandisers = merch_ref.get() or {}

    mid = record.get("merchandiser_id") or args.id
    if not mid:
        used = [int(m.group(1)) for k in merchandisers if (m := re.fullmatch(r"m-(\d+)", k))]
        mid = f"m-{(max(used) + 1 if used else 1):02d}"
    name = args.name or record.get("display_name") or user.display_name or args.email.split("@")[0]

    print(f"Account : {args.email}  uid={uid}")
    print(f"users/{uid} now: {record or '(no record)'}")
    for node in ("osa_reports", "sos_audits", "audits"):
        recs = get_ref(node).get() or {}
        n = sum(1 for r in recs.values() if isinstance(r, dict) and r.get("uid") == uid)
        print(f"  {node:12} {n} record(s) already submitted by this account")
    print(f"Will link as {mid} ({name})")
    if not args.yes:
        return print("\nDry run - nothing written. Re-run with --yes.")

    users_ref.child(uid).update({
        "email": record.get("email") or args.email,
        "display_name": name,
        "role": record.get("role") if record.get("role") in ("admin", "manager") else "merchandiser",
        "merchandiser_id": mid,
        "active": True,
        "created_at": record.get("created_at") or int(time.time() * 1000),
    })
    merch_ref.child(mid).update({"name": name, "uid": uid})
    print(f"Linked. {args.email} -> {mid}. Ask them to log out and back in on the phone.")


if __name__ == "__main__":
    main()

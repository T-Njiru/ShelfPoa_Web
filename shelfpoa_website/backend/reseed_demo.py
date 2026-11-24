r"""
reseed_demo.py  --  refresh the simulated audit data so it falls inside the dashboard's windows
================================================================================================
The Merchandiser performance page only counts the last 30 days (and "visits this month"). Seeded
data is dated relative to the day it was seeded, so after a month it ages out and the page goes
empty. This replaces the simulated records with a fresh set dated over the last --days days.

Run from backend\ (needs the service-account key in .env, like the other seed scripts):

    .\.venv\Scripts\python.exe reseed_demo.py              # DRY RUN: counts only, nothing changed
    .\.venv\Scripts\python.exe reseed_demo.py --yes        # replace the simulated data
    .\.venv\Scripts\python.exe reseed_demo.py --days 21 --yes

What it does, in order (only records with source == "simulated" are ever deleted; reports from
the mobile app and real accounts are never touched):
  1. remembers which login account belongs to each simulated merchandiser (merchandisers/m-xx/uid)
  2. deletes simulated  audits, sos_audits, merchandisers   (seed_audits.py --purge)
  3. deletes simulated  osa_reports                          (seed_osa_reports.py --purge)
  4. writes new osa_reports over the last --days days        (seed_osa_reports.py)
  5. writes matching audits, sos_audits, merchandisers       (seed_audits.py)
  6. puts the login-account links from step 1 back
The simulated login accounts (m01@shelfpoa.test ...) are kept, so their passwords still work.

Re-run it shortly before a demo: "visits this month" restarts on the 1st (Nairobi time).
"""

import argparse
from pathlib import Path

import seed_audits
import seed_osa_reports

OUTLETS_CSV = Path(__file__).resolve().parent / "app" / "ml" / "artifacts" / "outlet_subcounty_mapping.csv"


def simulated(records: dict | None) -> dict:
    return {k: None for k, r in (records or {}).items() if isinstance(r, dict) and r.get("source") == "simulated"}


def write(ref, records: dict):
    for chunk in seed_osa_reports.chunked(records):
        ref.update(chunk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="spread the new visits over the last N days (default 14)")
    ap.add_argument("--yes", action="store_true", help="actually replace the data (default is a dry run)")
    args = ap.parse_args()
    if not 1 <= args.days <= 28:
        raise SystemExit("--days must be between 1 and 28 so every visit stays inside the 30-day window.")

    from app.core.firebase import get_ref
    nodes = ("osa_reports", "audits", "sos_audits", "merchandisers")
    refs = {n: get_ref(n) for n in nodes}
    if any(r is None for r in refs.values()):
        raise SystemExit("Firebase isn't configured - see the warning above.")

    existing = {n: refs[n].get() or {} for n in nodes}
    old = {n: simulated(existing[n]) for n in nodes}
    links = {m: r["uid"] for m, r in existing["merchandisers"].items()
             if isinstance(r, dict) and r.get("source") == "simulated" and r.get("uid")}

    outlets = seed_osa_reports.load_outlets(str(OUTLETS_CSV))
    osa = seed_osa_reports.generate(outlets, days=args.days)
    merchandisers, audits, sos = seed_audits.build(osa)
    for m, uid in links.items():
        if m in merchandisers:
            merchandisers[m]["uid"] = uid
    stamps = sorted(r["timestamp"] for r in osa.values())

    print("Will delete (simulated only): " + ", ".join(f"{n} {len(old[n]):,}" for n in nodes))
    print(f"Will write: osa_reports {len(osa):,}, audits {len(audits):,}, sos_audits {len(sos):,}, "
          f"merchandisers {len(merchandisers)}  |  {len(outlets)} outlets, visits {stamps[0]} -> {stamps[-1]}")
    print(f"Current stock-outs after reseed: {seed_osa_reports.current_stockouts(osa)}; "
          f"login links kept for {len(links)} merchandiser(s)")
    if not args.yes:
        return print("\nDry run - nothing changed. Re-run with --yes.")

    for n in ("audits", "sos_audits", "merchandisers", "osa_reports"):
        write(refs[n], old[n])
        print(f"  deleted {len(old[n]):,} from {n}")
    write(refs["osa_reports"], osa)
    write(refs["audits"], audits)
    write(refs["sos_audits"], sos)
    refs["merchandisers"].update(merchandisers)
    print(f"  wrote {len(osa):,} osa_reports, {len(audits):,} audits, {len(sos):,} sos_audits, "
          f"{len(merchandisers)} merchandisers")
    print("Done. The dashboard picks this up within about a minute (or restart the backend).")


if __name__ == "__main__":
    main()

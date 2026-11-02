r"""
seed_outlets.py  --  add the 75 supermarket outlets to `outlets_universe`
==========================================================================
Place in backend/ next to seed_osa_reports.py (it imports from it). Run with the venv Python:

    .\.venv\Scripts\python.exe seed_outlets.py --outlets .\app\ml\artifacts\outlet_subcounty_mapping.csv          # dry run
    .\.venv\Scripts\python.exe seed_outlets.py --outlets .\app\ml\artifacts\outlet_subcounty_mapping.csv --yes    # write
    .\.venv\Scripts\python.exe seed_outlets.py --purge --yes                                                         # remove simulated outlets only

Record shape matches your existing outlets_universe records:
    group_name   "Naivas"                 (the chain)
    outlet_name  "Naivas Westlands"       ("<group> <branch>")
    created_at   epoch milliseconds
plus two extra fields the API passes through:
    sub_county   "WESTLANDS"
    source       "simulated"              (what --purge matches on; legacy records are never touched)

Keys are slugs ("naivas-westlands"), the SAME ids seed_osa_reports.py puts in osa_reports.outlet_id,
so stockout alerts join to outlets. Slug keys also make this idempotent: re-running overwrites the
same 75 records instead of adding duplicates.

ML link: chain = group_name, branch = outlet_name minus the "<group> " prefix, e.g.
"Quickmart Kilimani" -> chain "Quickmart", branch "Kilimani" -> /api/forecast works for it.
"""

import argparse
import time

from seed_osa_reports import load_outlets, slug


def build(outlets: list[dict], now_ms: int) -> dict:
    recs = {}
    for o in outlets:
        name = f"{o['chain']} {o['branch']}"
        recs[slug(name)] = {"group_name": o["chain"], "outlet_name": name,
                            "sub_county": o["sub_county"], "created_at": now_ms, "source": "simulated"}
    if len(recs) != len(outlets):
        raise SystemExit("Two outlets produced the same slug - cannot seed safely.")
    return recs


def legacy_collisions(existing: dict, recs: dict) -> list[str]:
    """Names of seeded outlets that also exist as non-simulated (legacy/real) records."""
    legacy = {v.get("outlet_name", "").lower() for v in existing.values()
              if isinstance(v, dict) and v.get("source") != "simulated"}
    return sorted(r["outlet_name"] for r in recs.values() if r["outlet_name"].lower() in legacy)


def write(ref, recs: dict):
    ref.update(recs)  # one request, 75 records


def purge(ref) -> int:
    existing = ref.get() or {}
    doomed = {k: None for k, v in existing.items() if isinstance(v, dict) and v.get("source") == "simulated"}
    if doomed:
        ref.update(doomed)
    return len(doomed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outlets", help="outlet_subcounty_mapping.csv (needed unless --purge)")
    ap.add_argument("--purge", action="store_true", help="delete records with source == 'simulated'")
    ap.add_argument("--yes", action="store_true", help="actually write/delete (default is a dry run)")
    args = ap.parse_args()

    from app.core.firebase import get_ref
    ref = get_ref("outlets_universe")

    if args.purge:
        if ref is None:
            raise SystemExit("Firebase isn't configured - see the warning above.")
        existing = ref.get() or {}
        n = sum(1 for v in existing.values() if isinstance(v, dict) and v.get("source") == "simulated")
        print(f"{n} simulated outlet(s) of {len(existing)} total in outlets_universe")
        if not args.yes:
            return print("Dry run - re-run with --yes to delete.")
        return print(f"Deleted {purge(ref)}.")

    if not args.outlets:
        raise SystemExit("--outlets is required (path to outlet_subcounty_mapping.csv)")
    recs = build(load_outlets(args.outlets), int(time.time() * 1000))
    print(f"{len(recs)} outlets to seed, e.g. {next(iter(recs))!r}: {recs[next(iter(recs))]}")

    if ref is not None:
        existing = ref.get() or {}
        print(f"outlets_universe currently has {len(existing)} record(s)")
        clash = legacy_collisions(existing, recs)
        if clash:
            print("NOTE: these already exist under push keys and would appear twice - delete the old "
                  "ones in the Firebase console if they're legacy test data:\n   " + "\n   ".join(clash))

    if not args.yes:
        return print("\nDry run - nothing written. Re-run with --yes to write to outlets_universe.")
    if ref is None:
        raise SystemExit("Firebase isn't configured - see the warning above.")
    write(ref, recs)
    print("Done. Remove later with:  seed_outlets.py --purge --yes")


if __name__ == "__main__":
    main()
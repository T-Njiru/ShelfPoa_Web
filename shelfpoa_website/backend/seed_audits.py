r"""
seed_audits.py  --  simulated `merchandisers`, `audits` and `sos_audits` for ShelfPoa
======================================================================================
Place in backend/ (next to seed_osa_reports.py) and run from there:

    .\.venv\Scripts\python.exe seed_audits.py                 # DRY RUN (prints counts + samples)
    .\.venv\Scripts\python.exe seed_audits.py --yes           # write
    .\.venv\Scripts\python.exe seed_audits.py --purge --yes   # delete simulated records in all 3 nodes

Run AFTER seed_osa_reports.py. Nothing here is random-from-scratch: every audit visit is
derived from the simulated osa_reports already in Firebase (same audit_id, outlet,
merchandiser, timestamp), so visits, availability and share of shelf all agree with each other.
Refuses to write if simulated audits already exist (purge first), so it can't duplicate.

Record contracts (what the mobile app should write once real audits start):

  merchandisers/{merchandiser_id}       key e.g. "m-01"
      name           str
      source         str   "simulated" for seeded data only

  audits/{push_id}                      one record per store visit
      audit_id       str   same id stamped on that visit's osa_reports / sos_audits records
      merchandiser_id str
      outlet_id      str   slug, same as outlets_universe keys
      branch_name    str
      sub_county     str   optional
      timestamp      str   ISO-8601 UTC "2026-10-08T09:41:07Z"
      skus_checked   int   optional

  sos_audits/{push_id}                  one record per SKU per visit (YOLOv8 share-of-shelf)
      audit_id, merchandiser_id, outlet_id, branch_name, sku, timestamp   as above
      share_of_shelf_pct     float  this SKU's facings / all spreads facings on the shelf x 100
      on_shelf_availability  bool
      planogram_compliant    bool
"""

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime

NAMES = {  # illustrative, fictional
    "m-01": "Brian Otieno", "m-02": "Faith Wanjiru", "m-03": "Kevin Mutua", "m-04": "Mercy Achieng",
    "m-05": "Dennis Kiprop", "m-06": "Grace Njeri", "m-07": "Samuel Omondi", "m-08": "Ann Wambui",
}
# Blueband's share of the whole spreads shelf, by chain: value chains stock fewer rival brands
CHAIN_BB_SHARE = {"Carrefour": 30, "Chandarana Foodplus": 32, "Naivas": 38, "Quickmart": 40,
                  "Cleanshelf": 42, "Magunas": 46, "AFCOS": 46}
FLAVOR_W = {"ORI": 0.42, "S4B": 0.28, "CHOCO": 0.20, "VANILLA": 0.10}
SIZE_W = {"100g": 0.30, "250g": 0.30, "500g": 0.25, "1Kg": 0.15}
NODES = ("merchandisers", "audits", "sos_audits")
PUSH_CHARS = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"


def push_id(ts_ms: int, rng: random.Random) -> str:
    chars, ts = [], ts_ms
    for _ in range(8):
        chars.append(PUSH_CHARS[ts % 64])
        ts //= 64
    return "".join(reversed(chars)) + "".join(rng.choice(PUSH_CHARS) for _ in range(12))


def ts_ms(iso: str) -> int:
    return int(datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").timestamp() * 1000)


def chain_of(branch_name: str) -> str:
    return next((c for c in CHAIN_BB_SHARE if branch_name.startswith(c)), "Naivas")


def sku_weight(sku: str) -> float:
    _, flavor, size = sku.split(" ")
    return FLAVOR_W.get(flavor, 0.1) * SIZE_W.get(size, 0.2)


def skill(merch_id: str) -> float:
    """Fixed per-merchandiser quality in [-1, 1], so some are consistently better than others."""
    return random.Random(f"skill-{merch_id}").uniform(-1, 1)


def build(osa: dict, seed: int = 7):
    """osa = {key: osa_reports record}. Returns (merchandisers, audits, sos_audits) dicts."""
    rng = random.Random(seed)
    visits = defaultdict(list)
    for rec in osa.values():
        if isinstance(rec, dict) and rec.get("source") == "simulated" and rec.get("audit_id"):
            visits[rec["audit_id"]].append(rec)

    merchandisers, audits, sos = {}, {}, {}
    for audit_id, readings in sorted(visits.items()):
        first = readings[0]
        m, ts = first.get("merchandiser_id", "m-00"), first["timestamp"]
        merchandisers.setdefault(m, {"name": NAMES.get(m, m), "source": "simulated"})
        base = {"audit_id": audit_id, "merchandiser_id": m, "outlet_id": first["outlet_id"],
                "branch_name": first["branch_name"], "timestamp": ts, "source": "simulated"}
        audits[push_id(ts_ms(ts), rng)] = {**base, "sub_county": first.get("sub_county", ""),
                                           "skus_checked": len(readings)}

        s = skill(m)
        bb_total = min(70.0, max(10.0, rng.gauss(CHAIN_BB_SHARE[chain_of(first["branch_name"])] + 5 * s, 4)))
        on_shelf = [r for r in readings if r["available"]]
        w = {r["sku"]: sku_weight(r["sku"]) * rng.uniform(0.7, 1.3) for r in on_shelf}
        w_sum = sum(w.values()) or 1.0
        p_plano = 0.78 + 0.13 * s
        for r in readings:
            avail = bool(r["available"])
            sos[push_id(ts_ms(ts), rng)] = {
                **base, "sku": r["sku"], "on_shelf_availability": avail,
                "share_of_shelf_pct": round(bb_total * w[r["sku"]] / w_sum, 2) if avail else 0.0,
                "planogram_compliant": avail and rng.random() < p_plano,
            }
    return merchandisers, audits, sos


def chunked(d: dict, size: int = 500):
    items = list(d.items())
    for i in range(0, len(items), size):
        yield dict(items[i:i + size])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge", action="store_true", help="delete source == 'simulated' records in all 3 nodes")
    ap.add_argument("--yes", action="store_true", help="actually write/delete (default is a dry run)")
    args = ap.parse_args()

    from app.core.firebase import get_ref
    refs = {n: get_ref(n) for n in NODES + ("osa_reports",)}
    if any(r is None for r in refs.values()):
        raise SystemExit("Firebase isn't configured - see the warning above.")

    if args.purge:
        for n in NODES:
            existing = refs[n].get() or {}
            doomed = {k: None for k, r in existing.items() if isinstance(r, dict) and r.get("source") == "simulated"}
            print(f"{n}: {len(doomed)} simulated of {len(existing)}")
            if args.yes:
                for chunk in chunked(doomed):
                    refs[n].update(chunk)
        return print("Deleted." if args.yes else "Dry run - re-run with --yes to delete.")

    already = sum(1 for r in (refs["audits"].get() or {}).values()
                  if isinstance(r, dict) and r.get("source") == "simulated")
    if already:
        raise SystemExit(f"audits already holds {already} simulated records. "
                         "Run with --purge --yes first if you want to re-seed.")

    merchandisers, audits, sos = build(refs["osa_reports"].get() or {})
    if not audits:
        raise SystemExit("No simulated osa_reports found - run seed_osa_reports.py first.")
    print(f"{len(merchandisers)} merchandisers, {len(audits)} audits, {len(sos):,} sos_audits records")
    for name, d in (("audits", audits), ("sos_audits", sos)):
        k = next(iter(d))
        print(f"sample {name}:", k, json.dumps(d[k]))

    if not args.yes:
        return print("\nDry run - nothing written. Re-run with --yes to write.")
    refs["merchandisers"].update(merchandisers)
    for n, d in (("audits", audits), ("sos_audits", sos)):
        for chunk in chunked(d):
            refs[n].update(chunk)
        print(f"  wrote {len(d):,} to {n}")
    print("Done. Remove later with:  seed_audits.py --purge --yes")


if __name__ == "__main__":
    main()

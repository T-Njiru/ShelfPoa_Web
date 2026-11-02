r"""
seed_osa_reports.py  --  put simulated YOLOv8 OSA readings into `osa_reports`
===============================================================================
Place in backend/ (next to .env) and run from there, so `app` is importable.

    python seed_osa_reports.py --outlets path\to\outlet_subcounty_mapping.csv          # DRY RUN
    python seed_osa_reports.py --outlets path\to\outlet_subcounty_mapping.csv --yes    # write
    python seed_osa_reports.py --purge --yes                                            # delete simulated only

Every record carries  source: "simulated"  so --purge removes exactly what this script
wrote and nothing the mobile app wrote. Purge before real audits start flowing.

Keys are generated in Firebase push-ID format (chronological, 20 chars), the same as the
mobile app's push() produces, so order_by_key() returns seeded and real records in true
time order. Writes are batched with update(), ~6 requests total instead of ~2,800.

Record contract (what the mobile app should write to osa_reports via push()):
    outlet_id        str   slug, e.g. "naivas-westlands"   (align with outlets_universe keys)
    branch_name      str   e.g. "Naivas Westlands"
    sub_county       str   optional
    sku              str   e.g. "BB VANILLA 250g"
    available        bool  False = empty facing detected
    confidence       float YOLOv8 detection confidence
    timestamp        str   ISO-8601 UTC, "2026-10-08T09:41:07Z"
    status           str   optional; "open" on unavailable readings
    audit_id, merchandiser_id   optional
"""

import argparse
import csv
import json
import random
import re
from datetime import datetime, timedelta, timezone

SKUS = [
    "BB CHOCO 100g", "BB CHOCO 250g", "BB CHOCO 500g", "BB CHOCO 1Kg",
    "BB ORI 100g", "BB ORI 250g", "BB ORI 500g", "BB ORI 1Kg",
    "BB S4B 100g", "BB S4B 250g", "BB S4B 500g", "BB S4B 1Kg",
    "BB VANILLA 250g", "BB VANILLA 500g", "BB VANILLA 1Kg",
]
SLOW_SKUS = {"BB VANILLA 1Kg", "BB CHOCO 1Kg", "BB S4B 1Kg", "BB VANILLA 500g"}  # stock out more

# Illustrative base probability that a SKU is found out of stock at a given audit
CHAIN_OUT_RATE = {"Carrefour": 0.04, "Chandarana Foodplus": 0.05, "Naivas": 0.08,
                  "Quickmart": 0.08, "Cleanshelf": 0.10, "Magunas": 0.15, "AFCOS": 0.15}
P_STILL_OUT = 0.55  # if it was out at the previous audit, chance it's still out

PUSH_CHARS = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"


def push_id(ts_ms: int, rng: random.Random) -> str:
    """Firebase push-ID: 8 chars of base-64 timestamp + 12 random chars."""
    chars, ts = [], ts_ms
    for _ in range(8):
        chars.append(PUSH_CHARS[ts % 64])
        ts //= 64
    return "".join(reversed(chars)) + "".join(rng.choice(PUSH_CHARS) for _ in range(12))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_outlets(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["sub_county"].strip()]  # blank = outside Nairobi County
    return [{"chain": r["chain"], "branch": r["branch"], "sub_county": r["sub_county"]} for r in rows]


def generate(outlets: list[dict], days: int = 7, seed: int = 42, now: datetime | None = None) -> dict:
    """Returns {push_key: record}. 2-3 audits per outlet over the last `days` days; each
    audit reads all 15 SKUs, and stock-out state persists between audits."""
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    out = {}
    for o in outlets:
        outlet_id = slug(f"{o['chain']} {o['branch']}")
        branch_name = f"{o['chain']} {o['branch']}"
        merch = f"m-{rng.randint(1, 8):02d}"
        base = CHAIN_OUT_RATE.get(o["chain"], 0.08)
        times = sorted(now - timedelta(seconds=rng.randint(3600, days * 86400))
                       for _ in range(rng.randint(2, 3)))
        was_out = {sku: False for sku in SKUS}
        for n, t in enumerate(times, 1):
            t = t.replace(microsecond=0)
            ts_iso = t.strftime("%Y-%m-%dT%H:%M:%SZ")
            for sku in SKUS:
                p = P_STILL_OUT if was_out[sku] else base * (1.8 if sku in SLOW_SKUS else 1.0)
                is_out = rng.random() < p
                was_out[sku] = is_out
                rec = {
                    "outlet_id": outlet_id, "branch_name": branch_name, "sub_county": o["sub_county"],
                    "sku": sku, "available": not is_out,
                    "confidence": round(rng.uniform(0.60, 0.95) if is_out else rng.uniform(0.70, 0.98), 2),
                    "timestamp": ts_iso, "audit_id": f"sim-{outlet_id}-{n}",
                    "merchandiser_id": merch, "source": "simulated",
                }
                if is_out:
                    rec["status"] = "open"
                out[push_id(int(t.timestamp() * 1000), rng)] = rec
    return out


def current_stockouts(records: dict) -> int:
    """How many (outlet, SKU) pairs are out of stock per their LATEST reading."""
    latest = {}
    for rec in records.values():
        pair = (rec["outlet_id"], rec["sku"])
        if pair not in latest or rec["timestamp"] > latest[pair]["timestamp"]:
            latest[pair] = rec
    return sum(1 for r in latest.values() if not r["available"])


def chunked(d: dict, size: int = 500):
    items = list(d.items())
    for i in range(0, len(items), size):
        yield dict(items[i:i + size])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outlets", help="outlet_subcounty_mapping.csv (needed unless --purge)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--purge", action="store_true", help="delete records with source == 'simulated'")
    ap.add_argument("--yes", action="store_true", help="actually write/delete (default is a dry run)")
    args = ap.parse_args()

    if args.purge:
        from app.core.firebase import get_ref
        ref = get_ref("osa_reports")
        if ref is None:
            raise SystemExit("Firebase isn't configured - see the warning above.")
        existing = ref.get() or {}
        doomed = {k: None for k, r in existing.items() if isinstance(r, dict) and r.get("source") == "simulated"}
        print(f"{len(doomed)} simulated record(s) of {len(existing)} total in osa_reports")
        if not args.yes:
            return print("Dry run - re-run with --yes to delete.")
        for chunk in chunked(doomed):
            ref.update(chunk)
        return print("Deleted.")

    if not args.outlets:
        raise SystemExit("--outlets is required (path to outlet_subcounty_mapping.csv)")
    outlets = load_outlets(args.outlets)
    records = generate(outlets, days=args.days)
    unavailable = sum(1 for r in records.values() if not r["available"])
    print(f"{len(outlets)} outlets -> {len(records):,} readings "
          f"({unavailable:,} unavailable); {current_stockouts(records)} current stock-outs")
    sample_key = next(iter(records))
    print("sample:", sample_key, json.dumps(records[sample_key]))

    if not args.yes:
        return print("\nDry run - nothing written. Re-run with --yes to write to osa_reports.")
    from app.core.firebase import get_ref
    ref = get_ref("osa_reports")
    if ref is None:
        raise SystemExit("Firebase isn't configured - see the warning above.")
    for i, chunk in enumerate(chunked(records), 1):
        ref.update(chunk)
        print(f"  wrote batch {i} ({len(chunk)} records)")
    print("Done. Remove later with:  python seed_osa_reports.py --purge --yes")


if __name__ == "__main__":
    main()
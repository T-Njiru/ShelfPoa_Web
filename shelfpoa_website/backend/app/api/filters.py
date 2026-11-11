"""
Checks the chain / branch / sku filters on the forecast and basket routes, so a typo gets a clear
422 instead of an empty list that looks like "no data".

    chain, branch, sku = filters.resolve(chain, branch, sku)

Matching ignores case and extra spaces and returns the stored spelling ("naivas" -> "Naivas").
Unknown value, or a branch that does not belong to the chain -> HTTP 422 with the reason.
"""
from functools import lru_cache

import pandas as pd
from fastapi import HTTPException

from app.ml import demand_model


@lru_cache(maxsize=1)
def _known() -> dict:
    df = pd.read_csv(demand_model.SALES_CSV_PATH, usecols=["chain", "branch", "sku"]).drop_duplicates()
    return {
        "chain": sorted(df["chain"].unique()),
        "branch": sorted(df["branch"].unique()),
        "sku": sorted(df["sku"].unique()),
        "pairs": set(zip(df["chain"], df["branch"])),
    }


def _key(text: str) -> str:
    return " ".join(text.lower().split())


def _match(kind: str, value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    options = _known()[kind]
    by_key = {_key(o): o for o in options}
    hit = by_key.get(_key(value))
    if hit is None:
        sample = ", ".join(options[:6]) + (" ..." if len(options) > 6 else "")
        raise HTTPException(422, f"Unknown {kind} '{value}'. Known {kind} values include: {sample}")
    return hit


def resolve(chain: str | None = None, branch: str | None = None, sku: str | None = None):
    chain, branch, sku = _match("chain", chain), _match("branch", branch), _match("sku", sku)
    if chain and branch and (chain, branch) not in _known()["pairs"]:
        raise HTTPException(422, f"{chain} has no branch called '{branch}'.")
    return chain, branch, sku

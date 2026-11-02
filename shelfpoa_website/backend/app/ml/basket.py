from app.ml.registry import registry


def get_rules(limit: int = 10, sku: str | None = None) -> list[dict]:
    df = registry.rules

    # single-item consequents only, so the same itemset doesn't repeat across splits
    df = df[df.consequents.map(len) == 1]

    if sku:
        df = df[df.antecedents.map(lambda a: sku in a)]

    df = df.sort_values(["lift", "confidence"], ascending=False).head(limit)

    return [
        {
            "antecedent": list(r.antecedents),
            "consequent": list(r.consequents),
            "support": float(r.support),
            "confidence": float(r.confidence),
            "lift": float(r.lift),
        }
        for r in df.itertuples()
    ]
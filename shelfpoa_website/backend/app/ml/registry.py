from pathlib import Path
import numpy as np, pandas as pd, xgboost as xgb

DIR = Path(__file__).parent / "artifacts"
CATS = ["chain","branch","sub_county","dominant_income_segment",
        "flavor","sku","dominant_promo_type"]

class Registry:
    ready = False
    def load(self):
        self.booster = xgb.Booster()
        self.booster.load_model(DIR / "demand_model_weekly.json")
        self.n_trees = int(self.booster.attr("best_iteration")) + 1  # 274
        r = pd.read_csv(DIR / "nairobi_supermarket_bb_complement_rules.csv")
        for c in ("antecedents", "consequents"):
            r[c] = r[c].str.split(", ")
        self.rules = r[
            ~r.antecedents.map(lambda a: "OTHERS" in a)
            & ~r.consequents.map(lambda c: "OTHERS" in c)
            & (r.lift >= 1.2)
        ].reset_index(drop=True)
        self.ready = True

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        df = df[self.booster.feature_names].copy()
        df[CATS] = df[CATS].astype("category")
        p = self.booster.predict(xgb.DMatrix(df, enable_categorical=True),
                                 iteration_range=(0, self.n_trees))
        return np.expm1(p).clip(min=0)   # remove expm1 if target wasn't log1p

registry = Registry()
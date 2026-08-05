"""Carrega o modelo e as features pre-computadas, e serve o ranking de recomendacoes.

Cold start: quando o user_id nao existe no parquet de features (nunca apareceu em
events.csv), nao ha `interactions` nem `user_affinity_match` calculaveis. Estrategia
adotada: tratamos o usuario como neutro em relacao a todos os produtos
(`interactions=0`, `user_affinity_match=0`) e deixamos o proprio modelo gerar o
score com base nas features de produto (price, avg_rating, popularity_score) --
na pratica isso aproxima o ranking de uma ordenacao por popularidade/qualidade do
produto, sem exigir um caminho de codigo separado do fluxo normal. Ver SOLUTION.md.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model" / "model.pkl"
FEATURES_PATH = BASE_DIR / "data" / "processed" / "user_product_features.parquet"
PRODUCTS_PATH = BASE_DIR / "data" / "products.csv"


@dataclass
class Recommendation:
    product_id: str
    score: float
    category: str
    price: float


class RecommendationService:
    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        features_path: Path = FEATURES_PATH,
        products_path: Path = PRODUCTS_PATH,
    ) -> None:
        with open(model_path, "rb") as f:
            artifact = pickle.load(f)
        self.model = artifact["model"]
        self.scaler = artifact["scaler"]
        self.feature_cols: list[str] = artifact["feature_cols"]

        self.features = pd.read_parquet(features_path).set_index("user_id")
        self.products = pd.read_csv(products_path).set_index("product_id")
        self.known_users = set(self.features.index.unique())

    def is_known_user(self, user_id: str) -> bool:
        return user_id in self.known_users

    def _score(self, feature_rows: pd.DataFrame) -> pd.Series:
        X = feature_rows[self.feature_cols]
        X_scaled = self.scaler.transform(X)
        return pd.Series(self.model.predict_proba(X_scaled)[:, 1], index=feature_rows.index)

    def recommend(self, user_id: str, top_n: int = 10) -> tuple[list[Recommendation], bool]:
        """Retorna (lista ranqueada, cold_start: bool)."""
        cold_start = not self.is_known_user(user_id)

        if cold_start:
            rows = self.products.copy()
            rows["product_id"] = rows.index
            rows["interactions"] = 0
            rows["user_affinity_match"] = 0
        else:
            rows = self.features.loc[[user_id]].copy()
            rows = rows.set_index("product_id", drop=False)

        rows["score"] = self._score(rows)
        rows = rows.sort_values("score", ascending=False).head(top_n)

        recs = [
            Recommendation(
                product_id=row["product_id"],
                score=float(row["score"]),
                category=row["category"],
                price=float(row["price"]),
            )
            for _, row in rows.iterrows()
        ]
        return recs, cold_start

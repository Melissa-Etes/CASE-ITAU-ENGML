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

import json
import pickle
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model" / "model.pkl"
MODEL_CARD_PATH = BASE_DIR / "model" / "model_card.json"
FEATURES_PATH = BASE_DIR / "data" / "processed" / "user_product_features.parquet"
PRODUCTS_PATH = BASE_DIR / "data" / "products.csv"


class ModelIntegrityError(RuntimeError):
    """Levantado quando o artefato carregado nao bate com o que o codigo espera.

    Existe para falhar o startup imediatamente (fail-fast) em vez de deixar o
    servico subir "aparentemente saudavel" e so quebrar no primeiro request real
    -- ou pior, produzir previsoes erradas silenciosamente porque as colunas
    entraram na ordem/quantidade errada no scaler/modelo.
    """


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
        model_card_path: Path = MODEL_CARD_PATH,
        features_path: Path = FEATURES_PATH,
        products_path: Path = PRODUCTS_PATH,
    ) -> None:
        with open(model_path, "rb") as f:
            artifact = pickle.load(f)
        self.model = artifact["model"]
        self.scaler = artifact["scaler"]
        self.feature_cols: list[str] = artifact["feature_cols"]

        with open(model_card_path, encoding="utf-8") as f:
            self.model_version: str = json.load(f)["version"]

        self._check_artifact_integrity()

        self.features = pd.read_parquet(features_path).set_index("user_id")
        self.products = pd.read_csv(products_path).set_index("product_id")
        self.known_users = set(self.features.index.unique())

    def _check_artifact_integrity(self) -> None:
        """Sanity check de startup: o scaler foi ajustado (fit) para o mesmo
        numero de colunas que feature_cols declara. Se alguem trocar o
        model.pkl por um artefato incompativel, queremos que o servico
        recuse subir, em vez de servir previsoes erradas silenciosamente.
        """
        n_expected = len(self.feature_cols)
        n_fitted = getattr(self.scaler, "n_features_in_", None)
        if n_fitted is not None and n_fitted != n_expected:
            raise ModelIntegrityError(
                f"artefato inconsistente: scaler foi ajustado para {n_fitted} features, "
                f"mas feature_cols declara {n_expected} ({self.feature_cols})"
            )

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

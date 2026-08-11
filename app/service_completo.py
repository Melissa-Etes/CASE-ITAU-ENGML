"""Classe que junta as pecas: carrega modelo/dados e delega a logica
de negocio para as funcoes puras em app/recomendador/.

Substitui totalmente app/model_service.py como Model da aplicacao (ver
app/dependencies.py e app/main.py) -- nao depende dele em nada, define seus
proprios Recommendation e ModelIntegrityError.
"""

import json
import pickle
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.recomendador import is_known_user, montar_candidatos, ordenar_candidatos_por_score, scores

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model"
FEATURES_PATH = BASE_DIR / "data" / "processed" / "user_product_features.parquet"
PRODUCTS_PATH = BASE_DIR / "data" / "products.csv"


class ModelIntegrityError(RuntimeError):
    """Levantado quando o artefato carregado nao bate com o que o codigo
    espera -- falha rapido no startup em vez de servir previsoes erradas
    em silencio."""


@dataclass
class Recommendation:
    product_id: str
    score: float
    category: str
    price: float


class Recomendador:
    # Carrega modelo, scaler, features e produtos UMA VEZ (chamado no
    # lifespan de app/main.py, nao a cada request). Falha rapido se o
    # artefato estiver inconsistente (_check_artifact_integrity).
    def __init__(self, model_path: Path = MODEL_PATH):
        with open(model_path / "model.pkl", "rb") as f:
            artifact = pickle.load(f)
        self.model = artifact["model"]
        self.scaler = artifact["scaler"]
        self.feature_cols = artifact["feature_cols"]
        with open(model_path / "model_card.json", "rb") as f:
            self.model_version = json.load(f)["version"]

        self._check_artifact_integrity()

        self.features = pd.read_parquet(FEATURES_PATH).set_index("user_id")
        self.products = pd.read_csv(PRODUCTS_PATH).set_index("product_id")
        self.known_users = set(self.features.index.unique())

        # mtime do parquet = quando o job de ingestao gerou esse snapshot.
        # Usado por app/main.py (metrica de idade dos dados) e pelo /health.
        self.features_generated_at: float = FEATURES_PATH.stat().st_mtime

    def _check_artifact_integrity(self) -> None:
        """Sanity check de startup: o scaler foi ajustado (fit) para o
        mesmo numero de colunas que feature_cols declara."""
        n_expected = len(self.feature_cols)
        n_fitted = getattr(self.scaler, "n_features_in_", None)
        if n_fitted is not None and n_fitted != n_expected:
            raise ModelIntegrityError(
                f"artefato inconsistente: scaler foi ajustado para {n_fitted} features, "
                f"mas feature_cols declara {n_expected} ({self.feature_cols})"
            )

    # Delega para a funcao pura importada, passando o known_users ja carregado
    def is_known_user(self, user_id: str) -> bool:
        return is_known_user(self.known_users, user_id)

    # Metodo principal: monta os candidatos (cold start ou historico real),
    # pontua e ordena por score, e converte o resultado para a lista de
    # Recommendation que o Controller (routers/) espera receber.
    def recommend(self, user_id: str, top_n: int = 10) -> tuple[list[Recommendation], bool]:
        cold_start = not self.is_known_user(user_id)

        candidatos = montar_candidatos(user_id, self.known_users, self.features, self.products)
        candidatos = ordenar_candidatos_por_score(candidatos, self.feature_cols, self.scaler, self.model, top_n)

        # Converte cada linha do DataFrame final num objeto Recommendation
        recs = [
            Recommendation(
                product_id=row["product_id"],
                score=float(row["score"]),
                category=row["category"],
                price=float(row["price"]),
            )
            for _, row in candidatos.iterrows()
        ]
        return recs, cold_start


if __name__ == "__main__":
    r = Recomendador(MODEL_PATH)
    recs, cold_start = r.recommend("u_0100")
    print(f"cold_start={cold_start}, {len(recs)} recomendacoes")
    for rec in recs[:3]:
        print(rec)

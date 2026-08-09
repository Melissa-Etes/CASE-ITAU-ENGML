"""Calcula o baseline de distribuicao de score usado pelo gate de qualidade
do modelo (tests/test_model_quality_gate.py) e pelo dashboard do Grafana
(observability/grafana/provisioning/dashboards/personalization-service.json).

Roda o modelo real (model/model.pkl) sobre o snapshot de features real
(data/processed/user_product_features.parquet) e reporta a distribuicao do
TOP-10 score por usuario -- ou seja, exatamente o que a API efetivamente
retorna em /recommendations/{user_id}, nao a distribuicao sobre todos os
pares usuario-produto (que seria mais baixa, porque inclui os produtos
"ruins" que nunca aparecem no top 10).

Uso:
    python -m ingestion.build_features   # garante que o parquet existe
    python scripts/compute_score_baseline.py
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model" / "model.pkl"
FEATURES_PATH = BASE_DIR / "data" / "processed" / "user_product_features.parquet"

TOP_N = 10


def main() -> None:
    with open(MODEL_PATH, "rb") as f:
        artifact = pickle.load(f)
    model = artifact["model"]
    scaler = artifact["scaler"]
    feature_cols = artifact["feature_cols"]

    features = pd.read_parquet(FEATURES_PATH)
    X = scaler.transform(features[feature_cols])
    features = features.copy()
    features["score"] = model.predict_proba(X)[:, 1]

    top_n_por_usuario = (
        features.sort_values("score", ascending=False)
        .groupby("user_id")
        .head(TOP_N)["score"]
    )

    print(f"Baseline de score (top-{TOP_N} por usuario, {features['user_id'].nunique()} usuarios):\n")
    print(top_n_por_usuario.describe())
    print()
    quantis = top_n_por_usuario.quantile([0.10, 0.50, 0.90])
    print("p10 / p50 / p90:")
    print(quantis.to_string())


if __name__ == "__main__":
    main()

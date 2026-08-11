"""Feature engineering: events.csv + products.csv -> user_id x product_id feature matrix.

Regras de derivação (documentadas também no SOLUTION.md):
- `interactions`: contagem de TODAS as linhas de events.csv para o par (user_id, product_id),
  independente do event_type (view/click/add_to_cart/purchase contam igual). O model_card não
  distingue por tipo de evento, então tratamos todo evento como sinal de interação.
- `user_affinity_match`: para cada usuário, a categoria com maior número de interações
  (todas as linhas de events.csv daquele usuário, join com products.csv por product_id).
  Desempate: em caso de contagem igual entre categorias, escolhemos a categoria com maior
  `popularity_score` médio entre os produtos empatados -- critério determinístico e razoável
  (na ausência de mais sinal, produtos mais populares são uma escolha mais segura).
"""

from __future__ import annotations

import pandas as pd


def compute_interactions(events: pd.DataFrame) -> pd.DataFrame:
    """Conta interações por (user_id, product_id)."""
    return (
        events.groupby(["user_id", "product_id"])
        .size()
        .reset_index(name="interactions")
    )


def compute_user_top_category(events: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Para cada usuário, retorna a categoria de maior afinidade histórica."""
    merged = events.merge(products[["product_id", "category", "popularity_score"]], on="product_id", how="left")

    counts = (
        merged.groupby(["user_id", "category"])
        .agg(count=("product_id", "size"), avg_popularity=("popularity_score", "mean"))
        .reset_index()
    )

    # ordena por contagem desc, depois popularidade média desc (desempate), depois categoria (determinismo)
    counts = counts.sort_values(
        by=["count", "avg_popularity", "category"],
        ascending=[False, False, True],
    )
    top = counts.groupby("user_id").head(1)[["user_id", "category"]]
    return top.rename(columns={"category": "top_category"})


def build_feature_matrix(events: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Gera a matriz completa user_id x product_id com as features esperadas pelo modelo.

    Cobre todos os usuários vistos em events.csv x todos os produtos do catálogo,
    para que o endpoint de recomendação possa ranquear qualquer produto para
    qualquer usuário conhecido (não só os que ele já interagiu).
    """
    # Produto cartesiano: todo usuario visto x todo produto do catalogo
    users = events[["user_id"]].drop_duplicates()
    matrix = users.merge(products, how="cross")

    # Gruda a contagem de interacoes real; pares sem interacao ficam com NaN -> 0
    interactions = compute_interactions(events)
    matrix = matrix.merge(interactions, on=["user_id", "product_id"], how="left")
    matrix["interactions"] = matrix["interactions"].fillna(0).astype(int)

    # Gruda a categoria favorita de cada usuario, e compara linha a linha
    # contra a categoria real do produto -> vira 0 ou 1
    top_category = compute_user_top_category(events, products)
    matrix = matrix.merge(top_category, on="user_id", how="left")
    matrix["user_affinity_match"] = (matrix["category"] == matrix["top_category"]).astype(int)

    feature_cols = ["interactions", "price", "avg_rating", "popularity_score", "user_affinity_match"]
    # `category` nao e feature do modelo, mas e mantida para exibicao na API sem re-join em request-time.
    return matrix[["user_id", "product_id", "category"] + feature_cols]

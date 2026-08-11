from .score import scores
import pandas as pd

# Monta a tabela de produtos candidatos a serem pontuados. Usuario
# desconhecido -> catalogo inteiro, com interactions/user_affinity_match
# zerados (cold start). Usuario conhecido -> so o historico real dele,
# ja vindo pronto do parquet de features.
def montar_candidatos(
        user_id: str,
        known_users: set,
        features: pd.DataFrame,
        products: pd.DataFrame
              
) -> pd.DataFrame:
    if user_id not in known_users:
        produtos_candidatos = products.copy()
        produtos_candidatos["product_id"] = produtos_candidatos.index
        produtos_candidatos["interactions"] = 0
        produtos_candidatos["user_affinity_match"] = 0
        return produtos_candidatos
    else:
        produtos_candidatos = features.loc[[user_id]].copy()
        produtos_candidatos = produtos_candidatos.set_index("product_id", drop=False)
        return produtos_candidatos


# Pontua cada candidato com o modelo (via scores()), ordena do maior score
# para o menor, e corta para as top_n primeiras linhas.
def ordenar_candidatos_por_score(
    produtos_candidatos: pd.DataFrame,
    feature_cols: list,
    scaler,
    model,
    top_n: int = 10,
) -> pd.DataFrame:
    produtos_candidatos["score"] = scores(produtos_candidatos, feature_cols, scaler, model)
    produtos_candidatos = produtos_candidatos.sort_values("score", ascending=False).head(top_n)
    return produtos_candidatos


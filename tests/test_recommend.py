"""Testes de app/recomendador/recommend.py

montar_candidatos() e ordenar_candidatos_por_score() sao funcoes puras que
recebem os dados prontos (features, products, scaler, model) -- por isso os
testes usam tabelas pequenas "de mentira" em vez do parquet/csv reais, sem
precisar carregar o modelo inteiro so para testar a logica de montagem e
ordenacao.
"""

import pandas as pd

import app.recomendador.recommend as recommend_module
from app.recomendador.recommend import montar_candidatos, ordenar_candidatos_por_score


def _products_de_mentira() -> pd.DataFrame:
    """3 produtos, indexados por product_id (igual ao self.products real)."""
    return pd.DataFrame(
        {
            "category": ["casa", "livros", "moda"],
            "price": [10.0, 20.0, 30.0],
            "avg_rating": [4.0, 3.0, 5.0],
            "popularity_score": [0.5, 0.2, 0.9],
        },
        index=pd.Index(["p_001", "p_002", "p_003"], name="product_id"),
    )


def _features_de_mentira() -> pd.DataFrame:
    """Historico de "u_0001": ja interagiu com p_001 e p_002 (mas nao com
    p_003). Indexado por user_id, igual ao self.features real."""
    return pd.DataFrame(
        {
            "user_id": ["u_0001", "u_0001"],
            "product_id": ["p_001", "p_002"],
            "category": ["casa", "livros"],
            "interactions": [3, 1],
            "price": [10.0, 20.0],
            "avg_rating": [4.0, 3.0],
            "popularity_score": [0.5, 0.2],
            "user_affinity_match": [1, 0],
        }
    ).set_index("user_id")


# ---- montar_candidatos ----


def test_cold_start_devolve_catalogo_inteiro_com_zeros():
    """Usuario desconhecido -> a tabela de candidatos e o catalogo INTEIRO
    de produtos (3 linhas, nao so os que ele "interagiu", porque ele nao
    interagiu com nada), com interactions e user_affinity_match neutros
    (0), tratando o usuario como "sem preferencia conhecida"."""
    products = _products_de_mentira()

    candidatos = montar_candidatos(
        "usuario_novo",
        known_users=set(),
        features=pd.DataFrame(),
        products=products,
    )

    assert len(candidatos) == 3
    assert (candidatos["interactions"] == 0).all()
    assert (candidatos["user_affinity_match"] == 0).all()


def test_usuario_conhecido_devolve_so_o_historico_dele():
    """Usuario conhecido -> a tabela de candidatos e SO o que ja existe no
    historico dele (2 linhas: p_001 e p_002), com os valores reais de
    interactions/user_affinity_match ja calculados -- nada de zerar."""
    features = _features_de_mentira()

    candidatos = montar_candidatos(
        "u_0001",
        known_users={"u_0001"},
        features=features,
        products=_products_de_mentira(),
    )

    assert len(candidatos) == 2
    assert candidatos.loc["p_001", "interactions"] == 3
    assert candidatos.loc["p_002", "user_affinity_match"] == 0


# ---- ordenar_candidatos_por_score ----
#
# ordenar_candidatos_por_score() importa `scores` diretamente de score.py,
# em vez de recebe-la como parametro -- diferente de montar_candidatos, que
# recebe tudo pronto. Isso significa que nao dá pra so "passar uma funcao
# falsa" nos argumentos: para testar sem depender do model.pkl real, e
# preciso usar o fixture `monkeypatch` do pytest, que substitui
# temporariamente um nome dentro de um modulo, e desfaz a substituicao
# sozinho no final do teste (mesmo se o teste falhar no meio).


def test_ordenar_por_score_ordena_decrescente_e_corta_top_n(monkeypatch):
    candidatos = _products_de_mentira().copy()
    candidatos["interactions"] = 0
    candidatos["user_affinity_match"] = 0

    def scores_fake(produtos_candidatos, feature_cols, scaler, model):
        # scores inventados -- p_002 e o "melhor", p_003 o "pior" -- so
        # para confirmar que a ordenacao usa esses valores corretamente
        return pd.Series([0.3, 0.9, 0.1], index=produtos_candidatos.index)

    # troca o nome `scores` DENTRO do modulo recommend por nossa versao
    # falsa, apenas durante este teste
    monkeypatch.setattr(recommend_module, "scores", scores_fake)

    resultado = ordenar_candidatos_por_score(
        candidatos,
        feature_cols=["interactions", "price", "avg_rating", "popularity_score"],
        scaler=None,  # nao importa: scores_fake ignora esses parametros
        model=None,
        top_n=2,
    )

    assert len(resultado) == 2
    assert list(resultado.index) == ["p_002", "p_001"]  # 0.9 depois 0.3, nunca p_003 (0.1)


def test_ordenar_por_score_com_top_n_maior_que_candidatos_devolve_todos(monkeypatch):
    """Se top_n pedir mais linhas do que existem candidatos, .head(top_n)
    simplesmente devolve tudo que tem, sem erro."""
    candidatos = _products_de_mentira().copy()
    candidatos["interactions"] = 0
    candidatos["user_affinity_match"] = 0

    def scores_fake(produtos_candidatos, feature_cols, scaler, model):
        return pd.Series([0.5, 0.5, 0.5], index=produtos_candidatos.index)

    monkeypatch.setattr(recommend_module, "scores", scores_fake)

    resultado = ordenar_candidatos_por_score(
        candidatos,
        feature_cols=["interactions", "price", "avg_rating", "popularity_score"],
        scaler=None,
        model=None,
        top_n=1000,
    )

    assert len(resultado) == 3

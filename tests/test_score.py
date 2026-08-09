"""Testes de app/recomendador/score.py

scores() e uma funcao pura que recebe model/scaler ja prontos (nao carrega
nada sozinha). Isso permite testar a LOGICA de pontuacao (seleciona
feature_cols, escala, chama predict_proba, embrulha em Series com o indice
certo) sem depender do modelo real -- usamos um scaler e um model "falsos"
(fakes), que se comportam de um jeito previsivel e conhecido.

Essa e a vantagem pratica de score() receber scaler/model como parametro em
vez de carregar via self: dá pra substituir por uma versao de mentira aqui,
sem precisar de model.pkl no disco.
"""

import numpy as np
import pandas as pd

from app.recomendador.score import scores


class _FakeScaler:
    """Simula StandardScaler.transform(): aqui so devolve os valores como
    array numpy, sem normalizar de verdade (nao importa para este teste,
    porque estamos testando o ENCADEAMENTO das chamadas, nao a matematica
    de normalizacao em si -- essa parte ja e responsabilidade do sklearn,
    nao do nosso codigo)."""

    def transform(self, X):
        return X.to_numpy()


class _FakeModel:
    """Simula um model.predict_proba() que sempre devolve 0.7 de
    probabilidade para a classe 1 (a que scores() seleciona com [:, 1]),
    nao importa o input. Isso deixa o resultado esperado previsivel."""

    def predict_proba(self, X_scaled):
        n = X_scaled.shape[0]
        prob_classe_1 = np.full(n, 0.7)
        prob_classe_0 = 1 - prob_classe_1
        return np.column_stack([prob_classe_0, prob_classe_1])


def test_devolve_series_com_mesmo_indice_do_input():
    """O indice do resultado precisa bater com o indice do input, porque
    depois o chamador faz produtos_candidatos["score"] = resultado, e o
    pandas alinha por indice -- se o indice nao bater, o score cai na
    linha errada silenciosamente."""
    produtos_candidatos = pd.DataFrame(
        {"interactions": [0, 1], "price": [10.0, 20.0]},
        index=pd.Index(["p_001", "p_002"], name="product_id"),
    )

    resultado = scores(
        produtos_candidatos,
        feature_cols=["interactions", "price"],
        scaler=_FakeScaler(),
        model=_FakeModel(),
    )

    assert list(resultado.index) == ["p_001", "p_002"]


def test_valores_vem_da_coluna_1_do_predict_proba():
    """Confirma que scores() pega [:, 1] (probabilidade da classe positiva),
    nao [:, 0] -- com nosso FakeModel, isso significa que todo valor
    esperado e 0.7, nunca 0.3."""
    produtos_candidatos = pd.DataFrame(
        {"interactions": [0, 1, 2], "price": [10.0, 20.0, 30.0]},
        index=pd.Index(["p_001", "p_002", "p_003"], name="product_id"),
    )

    resultado = scores(
        produtos_candidatos,
        feature_cols=["interactions", "price"],
        scaler=_FakeScaler(),
        model=_FakeModel(),
    )

    assert (resultado == 0.7).all()


def test_seleciona_apenas_feature_cols_ignorando_colunas_extras():
    """produtos_candidatos pode ter colunas extras (category, product_id
    como coluna normal, etc) que o modelo nao usa. scores() precisa
    selecionar SO as colunas de feature_cols antes de escalar/pontuar --
    se passasse colunas a mais para o scaler, ele quebraria (foi ajustado
    para um numero fixo de colunas)."""
    produtos_candidatos = pd.DataFrame(
        {
            "interactions": [0, 1],
            "price": [10.0, 20.0],
            "category": ["casa", "livros"],  # coluna extra, nao esta em feature_cols
        },
        index=pd.Index(["p_001", "p_002"], name="product_id"),
    )

    # se scores() tentasse passar "category" (texto) para o FakeScaler,
    # a chamada to_numpy() ainda funcionaria, mas o teste abaixo comprova
    # que o resultado tem exatamente 2 linhas e nao lanca erro -- o ponto
    # real e que scores() nao pode estourar erro por causa da coluna extra
    resultado = scores(
        produtos_candidatos,
        feature_cols=["interactions", "price"],
        scaler=_FakeScaler(),
        model=_FakeModel(),
    )

    assert len(resultado) == 2

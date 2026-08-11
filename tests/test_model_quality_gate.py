"""Gate de qualidade do modelo: falha o build/CI se a distribuicao de score
do modelo carregado se desviar do baseline conhecido, ANTES de virar imagem
de producao.

Baseline calculado empiricamente sobre o modelo (purchase_propensity_v1,
LogisticRegression) + o snapshot de features atual, olhando o top-10
efetivamente servido por usuario: media 0.110, mediana 0.089, p10 0.070,
p90 0.184 (ver SOLUTION.md, secao 5).

Um desvio pra baixo (score medio perto de 0 -- modelo "zerado", features
quebradas) ou pra cima (saturacao do scaler, vazamento de feature,
user_affinity_match calculado errado) sao os dois sinais de alerta -- por
isso os limites sao verificados nos dois sentidos, nao so "nao caiu".

Este teste faz o mesmo papel que a recomendacao do guia da AWS de MLOps
("valide um novo modelo em um conjunto fixo e confirme que o desempenho
bate com um limite estabelecido; se for muito diferente, a build deve
falhar") -- sem depender de nenhuma ferramenta de nuvem.
"""

import pandas as pd
import pytest

from app.service_completo import Recomendador, MODEL_PATH

# Usuarios usados como amostra fixa para o gate -- os mesmos ja usados nos
# outros testes, para manter previsibilidade entre execucoes.
USUARIOS_CONHECIDOS_AMOSTRA = [f"u_{i:04d}" for i in range(0, 500, 25)]  # 20 usuarios

# Faixa aceitavel para a media de score do top-10 por usuario. Calibrada
# com folga em torno do baseline (0.110): alerta cedo, mas nao trava por
# ruido normal entre execucoes/pequenas mudancas de dado.
SCORE_MEDIO_MINIMO = 0.03
SCORE_MEDIO_MAXIMO = 0.35


@pytest.fixture(scope="module")
def r():
    return Recomendador(MODEL_PATH)


def test_score_medio_do_top10_por_usuario_dentro_do_baseline(r):
    todos_scores = []
    for user_id in USUARIOS_CONHECIDOS_AMOSTRA:
        if not r.is_known_user(user_id):
            continue
        recs, _ = r.recommend(user_id, top_n=10)
        todos_scores.extend(rec.score for rec in recs)

    scores = pd.Series(todos_scores)
    media = scores.mean()

    assert SCORE_MEDIO_MINIMO <= media <= SCORE_MEDIO_MAXIMO, (
        f"score medio do top-10 por usuario fora do baseline esperado "
        f"({SCORE_MEDIO_MINIMO}-{SCORE_MEDIO_MAXIMO}): {media:.4f}. "
        f"Investigar antes de promover este modelo/dado para producao -- "
        f"pode indicar saturacao do scaler, feature quebrada, ou "
        f"user_affinity_match calculado incorretamente."
    )


def test_score_nao_esta_saturado_em_um_unico_valor(r):
    """Se o modelo/scaler estiver quebrado (ex: todas as features zeradas
    ou o scaler mal ajustado), e comum todos os scores colapsarem para o
    mesmo valor -- o desvio padrao ficaria proximo de 0. Um modelo saudavel
    diferencia produtos, entao espera-se variancia real entre eles."""
    recs, _ = r.recommend(USUARIOS_CONHECIDOS_AMOSTRA[0], top_n=10)
    scores = pd.Series([rec.score for rec in recs])

    assert scores.std() > 0.001, (
        f"scores quase identicos entre si (std={scores.std():.6f}) -- "
        f"sinal de modelo/scaler saturado, nao diferenciando produtos."
    )


def test_cold_start_score_medio_dentro_do_baseline(r):
    """O caminho de cold start (usuario sem historico) tem seu proprio
    baseline, mais baixo que o de usuario conhecido -- ver SOLUTION.md.
    Testado separado porque usa uma logica de scoring diferente
    (interactions/user_affinity_match zerados) e pode quebrar sem afetar o
    caminho de usuario conhecido."""
    recs, cold_start = r.recommend("usuario_que_nunca_existiu_9999", top_n=10)
    assert cold_start is True

    scores = pd.Series([rec.score for rec in recs])
    media = scores.mean()

    assert SCORE_MEDIO_MINIMO <= media <= SCORE_MEDIO_MAXIMO, (
        f"score medio de cold start fora do baseline esperado: {media:.4f}"
    )

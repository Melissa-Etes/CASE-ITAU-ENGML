"""Testes de app/service_completo.py -- a classe Recomendador, escrita como
exercicio, que junta model_service_treino.py + as funcoes puras de
app/recomendador/ (is_known_user, montar_candidatos,
ordenar_candidatos_por_score, scores).

Diferente dos testes de user_check/recommend/score (que usam dados falsos
pequenos), aqui carregamos o Recomendador com o MODELO E OS DADOS REAIS do
projeto -- por isso o fixture `r` tem scope="module": instancia uma vez so
(carregar parquet + csv + pickle e uma operacao "cara"), e reusa o mesmo
objeto em todos os testes deste arquivo.
"""

import json
import re

import pytest

from app.service_completo import Recomendador, MODEL_PATH

USER_ID_PATTERN = re.compile(r"^u_\d{4}$")

# u_0100 existe de verdade no parquet de features (usado nos testes manuais
# ao longo da conversa). Ajuste aqui se os dados de exemplo mudarem.
USER_ID_CONHECIDO = "u_0100"
USER_ID_DESCONHECIDO = "nao_existe_123"


@pytest.fixture(scope="module")
def r():
    return Recomendador(MODEL_PATH)


# ---- is_known_user ----


def test_is_known_user_true_para_usuario_existente(r):
    assert r.is_known_user(USER_ID_CONHECIDO) is True


def test_is_known_user_false_para_usuario_inexistente(r):
    assert r.is_known_user(USER_ID_DESCONHECIDO) is False


# ---- recommend: comportamento geral ----
#
# recommend() devolve (list[Recommendation], cold_start: bool) -- mesmo
# formato do RecommendationService de producao, para ser compativel com
# app/routers/recommendations.py (ver app/service_completo.py).


def test_recommend_usuario_conhecido_devolve_top_n_recomendacoes(r):
    recs, cold_start = r.recommend(USER_ID_CONHECIDO, top_n=5)

    assert len(recs) == 5


def test_recommend_usuario_conhecido_tem_cold_start_false(r):
    _, cold_start = r.recommend(USER_ID_CONHECIDO)

    assert cold_start is False


def test_recommend_cold_start_nao_estoura_erro(r):
    """Antes de implementarmos o cold start, isso dava KeyError (o usuario
    nao existe no indice de self.features). Este teste documenta que esse
    bug foi corrigido -- se alguem reintroduzir o bug sem querer, este
    teste falha imediatamente apontando pra ca."""
    r.recommend(USER_ID_DESCONHECIDO)  # nao deve lancar excecao


def test_recommend_usuario_desconhecido_tem_cold_start_true(r):
    _, cold_start = r.recommend(USER_ID_DESCONHECIDO)

    assert cold_start is True


def test_recommend_cada_item_tem_os_4_campos_esperados(r):
    recs, _ = r.recommend(USER_ID_CONHECIDO, top_n=3)

    for rec in recs:
        assert isinstance(rec.product_id, str)
        assert isinstance(rec.score, float)
        assert isinstance(rec.category, str)
        assert isinstance(rec.price, float)


def test_recommend_ordenado_do_maior_score_para_o_menor(r):
    recs, _ = r.recommend(USER_ID_CONHECIDO)
    scores_obtidos = [rec.score for rec in recs]

    assert scores_obtidos == sorted(scores_obtidos, reverse=True)


# ---- Integridade do modelo: mesma versao, mesmas features ----
# Le o model_card.json direto (fonte da verdade), e compara contra o que o
# Recomendador efetivamente carregou em memoria. Isso pega, por exemplo, o
# caso de alguem trocar o model.pkl sem atualizar o model_card.json (ou
# vice-versa) -- os dois ficariam "descasados" e esses testes acusariam.


@pytest.fixture(scope="module")
def model_card():
    with open(MODEL_PATH / "model_card.json", encoding="utf-8") as f:
        return json.load(f)


def test_model_version_bate_com_model_card(r, model_card):
    assert r.model_version == model_card["version"]


def test_feature_cols_bate_com_model_card(r, model_card):
    # comparacao de LISTA, nao de set -- a ordem importa, porque e a ordem
    # que o scaler/modelo espera receber as colunas (ver score.py)
    assert r.feature_cols == model_card["input_features"]


def test_scaler_foi_ajustado_para_mesma_quantidade_de_feature_cols(r):
    """O StandardScaler guarda em n_features_in_ quantas colunas ele viu
    durante o fit (treino). Se isso nao bater com len(feature_cols), quer
    dizer que o artefato do modelo esta inconsistente -- o mesmo tipo de
    checagem que o model_service.py de producao faz no startup
    (_check_artifact_integrity), so que aqui como teste automatizado."""
    assert r.scaler.n_features_in_ == len(r.feature_cols)


# ---- Integridade dos dados: formato do user_id (u_ + 4 digitos, minusculo) ----
# Isso testa os DADOS carregados (o parquet), nao a validacao de input da
# API (essa ja existe, em app/validation.py, e ja e testada em
# tests/test_validation.py -- e uma camada diferente, que roda ANTES do
# Recomendador, na borda da API).


def test_todos_os_known_users_seguem_o_formato_esperado(r):
    assert all(USER_ID_PATTERN.match(uid) for uid in r.known_users)


def test_todos_os_known_users_sao_minusculos(r):
    assert all(uid == uid.lower() for uid in r.known_users)


def test_recommend_com_lixo_tambem_cai_em_cold_start_sem_erro(r):
    """O Recomendador (diferente da API real, que tem app/validation.py na
    frente) NAO valida formato -- ele so checa known_users. Por isso um
    user_id tipo "ksajdhakjsd" (claramente nao segue o formato u_XXXX) nao
    da erro aqui: ele cai no mesmo caminho de cold start que um user_id
    valido-mas-desconhecido. A diferenciacao entre "lixo" e "usuario novo
    legitimo" e responsabilidade de uma camada anterior (validacao de
    input), nao do Recomendador."""
    r.recommend("ksajdhakjsd")  # nao deve lancar excecao

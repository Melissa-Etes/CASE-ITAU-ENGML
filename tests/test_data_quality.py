"""Validacao de esquema e qualidade dos dados REAIS de entrada
(data/events.csv, data/products.csv) -- nao dos dados sinteticos usados em
test_features.py.

Diferenca de proposito: test_features.py garante que o CODIGO de
ingestion/features.py calcula certo dado um input conhecido. Este arquivo
garante que o DADO real que entra no pipeline continua no formato esperado
-- pega silenciosamente uma mudanca de schema, um valor fora de faixa, ou
uma categoria nova que o pipeline nao esperava, antes que isso vire uma
feature quebrada sem ninguem perceber.

Roda no CI (pytest -v, sem path restrito, coleta este arquivo junto).
"""

from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CATEGORIAS_CONHECIDAS = {"beleza", "casa", "eletronicos", "esporte", "livros", "moda"}
EVENT_TYPES_CONHECIDOS = {"view", "click", "add_to_cart", "purchase"}


@pytest.fixture(scope="module")
def events() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "events.csv")


@pytest.fixture(scope="module")
def products() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "products.csv")


# ---- events.csv ----


def test_events_tem_as_colunas_esperadas(events):
    assert set(events.columns) == {"user_id", "product_id", "event_type", "timestamp"}


def test_events_sem_valores_nulos_em_colunas_obrigatorias(events):
    assert events[["user_id", "product_id", "event_type", "timestamp"]].isnull().sum().sum() == 0


def test_events_event_type_dentro_do_conjunto_conhecido(events):
    tipos_inesperados = set(events["event_type"].unique()) - EVENT_TYPES_CONHECIDOS
    assert not tipos_inesperados, (
        f"event_type(s) nao esperados encontrados em events.csv: {tipos_inesperados}. "
        f"Se forem legitimos, atualizar EVENT_TYPES_CONHECIDOS e revisar "
        f"compute_interactions (ingestion/features.py), que hoje trata todos "
        f"os tipos igualmente."
    )


def test_events_product_id_referenciados_existem_no_catalogo(events, products):
    produtos_desconhecidos = set(events["product_id"]) - set(products["product_id"])
    assert not produtos_desconhecidos, (
        f"events.csv referencia product_id(s) que nao existem em products.csv: "
        f"{produtos_desconhecidos}. Isso quebraria o merge em build_feature_matrix."
    )


# ---- products.csv ----


def test_products_tem_as_colunas_esperadas(products):
    assert set(products.columns) == {"product_id", "category", "price", "avg_rating", "popularity_score"}


def test_products_sem_valores_nulos(products):
    assert products.isnull().sum().sum() == 0


def test_products_product_id_e_unico(products):
    assert products["product_id"].is_unique


def test_products_category_dentro_do_conjunto_conhecido(products):
    categorias_inesperadas = set(products["category"].unique()) - CATEGORIAS_CONHECIDAS
    assert not categorias_inesperadas, (
        f"categoria(s) nao esperada(s) em products.csv: {categorias_inesperadas}. "
        f"Se forem legitimas, atualizar CATEGORIAS_CONHECIDAS neste teste."
    )


def test_products_price_e_positivo(products):
    assert (products["price"] > 0).all(), "encontrado price <= 0 em products.csv"


def test_products_avg_rating_dentro_da_escala_0_a_5(products):
    assert products["avg_rating"].between(0, 5).all(), (
        "encontrado avg_rating fora da escala 0-5 em products.csv"
    )


def test_products_popularity_score_dentro_de_0_a_1(products):
    assert products["popularity_score"].between(0, 1).all(), (
        "encontrado popularity_score fora de 0-1 em products.csv -- "
        "o model_card.json documenta esse campo como '0-1'"
    )

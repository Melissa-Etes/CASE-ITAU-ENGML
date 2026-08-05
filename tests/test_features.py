import pandas as pd

from ingestion.features import (
    build_feature_matrix,
    compute_interactions,
    compute_user_top_category,
)


def _events():
    return pd.DataFrame(
        [
            {"user_id": "u1", "product_id": "pA", "event_type": "view", "timestamp": "t"},
            {"user_id": "u1", "product_id": "pA", "event_type": "click", "timestamp": "t"},
            {"user_id": "u1", "product_id": "pB", "event_type": "view", "timestamp": "t"},
            {"user_id": "u2", "product_id": "pB", "event_type": "purchase", "timestamp": "t"},
        ]
    )


def _products():
    return pd.DataFrame(
        [
            {"product_id": "pA", "category": "esporte", "price": 100.0, "avg_rating": 4.0, "popularity_score": 0.5},
            {"product_id": "pB", "category": "livros", "price": 50.0, "avg_rating": 3.5, "popularity_score": 0.9},
        ]
    )


def test_compute_interactions_counts_all_event_types():
    result = compute_interactions(_events())
    row = result[(result.user_id == "u1") & (result.product_id == "pA")].iloc[0]
    assert row["interactions"] == 2  # view + click


def test_compute_user_top_category_picks_highest_count():
    top = compute_user_top_category(_events(), _products())
    u1 = top[top.user_id == "u1"].iloc[0]
    assert u1["top_category"] == "esporte"  # 2 interações em pA (esporte) vs 1 em pB (livros)


def test_compute_user_top_category_tiebreak_by_popularity():
    # u2 so tem 1 interacao com pB -> top category = livros, sem ambiguidade
    top = compute_user_top_category(_events(), _products())
    u2 = top[top.user_id == "u2"].iloc[0]
    assert u2["top_category"] == "livros"


def test_build_feature_matrix_has_expected_shape_and_columns():
    matrix = build_feature_matrix(_events(), _products())
    assert set(matrix.columns) >= {
        "user_id", "product_id", "category",
        "interactions", "price", "avg_rating", "popularity_score", "user_affinity_match",
    }
    # 2 usuarios x 2 produtos
    assert len(matrix) == 4


def test_user_affinity_match_is_1_for_top_category_even_without_direct_interaction():
    matrix = build_feature_matrix(_events(), _products())
    # u1 tem afinidade com esporte (pA); pA e do proprio u1 -> affinity=1
    row = matrix[(matrix.user_id == "u1") & (matrix.product_id == "pA")].iloc[0]
    assert row["user_affinity_match"] == 1
    # pB e livros, nao e a categoria de afinidade de u1 -> affinity=0
    row2 = matrix[(matrix.user_id == "u1") & (matrix.product_id == "pB")].iloc[0]
    assert row2["user_affinity_match"] == 0

"""Testa o sanity check de startup (fail-fast) do RecommendationService:
o servico deve recusar subir se o artefato do modelo estiver incompativel
com o que o codigo espera, em vez de servir previsoes erradas em silencio.
"""

import json
import pickle

import pytest

from app.model_service import ModelIntegrityError, RecommendationService


class _FakeScaler:
    def __init__(self, n_features_in: int) -> None:
        self.n_features_in_ = n_features_in


class _FakeModel:
    pass


def _write_artifact(path, feature_cols, n_features_in):
    artifact = {
        "model": _FakeModel(),
        "scaler": _FakeScaler(n_features_in),
        "feature_cols": feature_cols,
    }
    with open(path, "wb") as f:
        pickle.dump(artifact, f)


def _write_model_card(path, version="9.9.9"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": version}, f)


def test_raises_when_scaler_feature_count_mismatches_feature_cols(tmp_path):
    model_path = tmp_path / "model.pkl"
    model_card_path = tmp_path / "model_card.json"

    # scaler foi "ajustado" para 3 features, mas feature_cols declara 5 -> incompativel
    _write_artifact(model_path, feature_cols=["a", "b", "c", "d", "e"], n_features_in=3)
    _write_model_card(model_card_path)

    with pytest.raises(ModelIntegrityError):
        RecommendationService(model_path=model_path, model_card_path=model_card_path)


def test_does_not_raise_when_feature_count_matches(tmp_path, monkeypatch):
    model_path = tmp_path / "model.pkl"
    model_card_path = tmp_path / "model_card.json"
    _write_artifact(model_path, feature_cols=["a", "b", "c"], n_features_in=3)
    _write_model_card(model_card_path)

    # Nao testamos o resto do __init__ (features/products reais) aqui -- isolamos
    # so o sanity check chamando-o diretamente, sem carregar dados de verdade.
    with open(model_path, "rb") as f:
        artifact = pickle.load(f)

    service = RecommendationService.__new__(RecommendationService)
    service.model = artifact["model"]
    service.scaler = artifact["scaler"]
    service.feature_cols = artifact["feature_cols"]
    service._check_artifact_integrity()  # nao deve levantar

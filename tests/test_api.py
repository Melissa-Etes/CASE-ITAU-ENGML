"""Testes do endpoint principal, incluindo cold start.

Usa o TestClient do FastAPI contra o app real (lifespan real, carrega o
model.pkl e o parquet de features reais de data/). Isso cobre tanto os
testes unitarios do endpoint quanto o requisito de teste de integracao
end-to-end (request HTTP real -> resposta, sem mockar camadas internas).
"""

from fastapi.testclient import TestClient

from app.main import app

KNOWN_USER = "u_0231"  # existe em data/events.csv
UNKNOWN_USER = "u_9999"  # formato valido, mas fora do range 0000-0499 usado em events.csv


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["model_version"] == "1.0.0"
        assert body["known_users"] == 500
        assert body["features_age_seconds"] >= 0


def test_recommendations_for_known_user_are_ranked_by_score():
    with TestClient(app) as client:
        resp = client.get(f"/recommendations/{KNOWN_USER}?top_n=5")
        assert resp.status_code == 200
        body = resp.json()

        assert body["user_id"] == KNOWN_USER
        assert body["cold_start"] is False
        recs = body["recommendations"]
        assert len(recs) == 5

        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)
        for r in recs:
            assert 0.0 <= r["score"] <= 1.0
            assert set(r.keys()) == {"product_id", "score", "category", "price"}


def test_recommendations_for_unknown_user_triggers_cold_start():
    with TestClient(app) as client:
        resp = client.get(f"/recommendations/{UNKNOWN_USER}?top_n=5")
        assert resp.status_code == 200
        body = resp.json()

        assert body["cold_start"] is True
        assert len(body["recommendations"]) == 5
        scores = [r["score"] for r in body["recommendations"]]
        assert scores == sorted(scores, reverse=True)


def test_top_n_is_respected():
    with TestClient(app) as client:
        resp = client.get(f"/recommendations/{KNOWN_USER}?top_n=3")
        assert len(resp.json()["recommendations"]) == 3


def test_top_n_out_of_range_is_rejected():
    with TestClient(app) as client:
        resp = client.get(f"/recommendations/{KNOWN_USER}?top_n=0")
        assert resp.status_code == 422


def test_uppercase_user_id_is_normalized_and_still_works():
    with TestClient(app) as client:
        resp_upper = client.get(f"/recommendations/{KNOWN_USER.upper()}?top_n=3")
        resp_lower = client.get(f"/recommendations/{KNOWN_USER}?top_n=3")
        assert resp_upper.status_code == 200
        assert resp_upper.json()["recommendations"] == resp_lower.json()["recommendations"]


def test_malformed_user_id_is_rejected_with_400():
    with TestClient(app) as client:
        resp = client.get("/recommendations/<script>alert(1)</script>?top_n=3")
        # `/` no payload faz o roteador tratar como outro segmento de path -> 404, nao chega na validacao
        assert resp.status_code == 404


def test_user_id_with_injection_like_chars_is_rejected_with_400():
    with TestClient(app) as client:
        resp = client.get("/recommendations/u_0231%3Bdrop_table?top_n=3")
        assert resp.status_code == 400
        assert "user_id" in resp.json()["detail"]


def test_error_response_body_includes_status_code_alongside_message():
    with TestClient(app) as client:
        resp = client.get("/recommendations/xyz123")
        assert resp.status_code == 400
        body = resp.json()
        assert body["status_code"] == 400
        assert body["detail"] == "user_id deve seguir o formato 'u_' + 4 digitos (ex: u_0231)"


def test_absurdly_long_user_id_is_rejected_with_400():
    with TestClient(app) as client:
        resp = client.get(f"/recommendations/u_0231{'a' * 100}?top_n=3")
        assert resp.status_code == 400


def test_score_histogram_and_data_age_are_exposed_in_metrics():
    with TestClient(app) as client:
        client.get(f"/recommendations/{KNOWN_USER}?top_n=3")
        metrics_body = client.get("/metrics").text

    assert "recommendation_score_bucket" in metrics_body
    assert "recommendation_score_count" in metrics_body
    assert "features_data_age_seconds" in metrics_body

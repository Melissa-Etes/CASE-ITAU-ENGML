"""Controller: recebe a requisicao HTTP, chama o Model, formata na View.

Nao calcula recomendacao (isso e trabalho do Model, em app/service_completo.py)
e nao define o formato da resposta (isso e a View, em app/schemas.py) -- so
orquestra: valida input, chama o service, loga, mede, devolve.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_service
from app.logging_config import get_logger
from app.metrics import RECOMMENDATION_REQUESTS, RECOMMENDATION_SCORE
from app.service_completo import Recomendador
from app.schemas import HealthResponse, RecommendationItem, RecommendationsResponse
from app.validation import InvalidUserIdError, normalize_user_id

logger = get_logger(__name__)

router = APIRouter()


# Reporta status geral: versao do modelo carregado, quantos usuarios
# conhecidos existem, e ha quanto tempo o snapshot de features foi gerado.
@router.get("/health", response_model=HealthResponse)
def health(service: Recomendador = Depends(get_service)):
    return HealthResponse(
        status="ok",
        model_version=service.model_version,
        known_users=len(service.known_users),
        features_age_seconds=round(time.time() - service.features_generated_at, 1),
    )


# Endpoint principal: valida o user_id, pede a recomendacao ao service,
# registra metricas/log, e formata a resposta no schema publico da API.
@router.get("/recommendations/{user_id}", response_model=RecommendationsResponse)
def get_recommendations(
    user_id: str,
    top_n: int = Query(default=10, ge=1, le=60),
    service: Recomendador = Depends(get_service),
):
    # Formato invalido -> 400, antes de tocar no service/modelo
    try:
        user_id = normalize_user_id(user_id)
    except InvalidUserIdError as exc:
        logger.warning("invalid_user_id", raw_user_id=exc.user_id, reason=exc.reason)
        raise HTTPException(status_code=400, detail=exc.reason) from exc

    # Mede quanto tempo o calculo da recomendacao leva, para logar como latency_ms
    start = time.perf_counter()
    recs, cold_start = service.recommend(user_id, top_n=top_n)
    latency_ms = (time.perf_counter() - start) * 1000

    # Metricas Prometheus: conta o request (por cold_start) e observa cada score servido
    RECOMMENDATION_REQUESTS.labels(cold_start=str(cold_start).lower()).inc()
    for r in recs:
        RECOMMENDATION_SCORE.observe(r.score)

    # Log estruturado (JSON) com os campos pedidos: user_id, latencia, cold_start
    logger.info(
        "recommendations_served",
        user_id=user_id,
        top_n=top_n,
        cold_start=cold_start,
        result_count=len(recs),
        latency_ms=round(latency_ms, 2),
    )

    # Converte a lista de Recommendation (dataclass interno) para o schema publico
    return RecommendationsResponse(
        user_id=user_id,
        cold_start=cold_start,
        model_version=service.model_version,
        recommendations=[
            RecommendationItem(
                product_id=r.product_id,
                score=r.score,
                category=r.category,
                price=r.price,
            )
            for r in recs
        ],
    )

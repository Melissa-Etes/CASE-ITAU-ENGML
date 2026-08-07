"""Controller: recebe a requisicao HTTP, chama o Model, formata na View.

Nao calcula recomendacao (isso e trabalho do Model, em app/model_service.py)
e nao define o formato da resposta (isso e a View, em app/schemas.py) -- so
orquestra: valida input, chama o service, loga, mede, devolve.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_service
from app.logging_config import get_logger
from app.metrics import RECOMMENDATION_REQUESTS
from app.model_service import RecommendationService
from app.schemas import HealthResponse, RecommendationItem, RecommendationsResponse
from app.validation import InvalidUserIdError, normalize_user_id

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(service: RecommendationService = Depends(get_service)):
    return HealthResponse(
        status="ok",
        model_version=service.model_version,
        known_users=len(service.known_users),
    )


@router.get("/recommendations/{user_id}", response_model=RecommendationsResponse)
def get_recommendations(
    user_id: str,
    top_n: int = Query(default=10, ge=1, le=60),
    service: RecommendationService = Depends(get_service),
):
    try:
        user_id = normalize_user_id(user_id)
    except InvalidUserIdError as exc:
        logger.warning("invalid_user_id", raw_user_id=exc.user_id, reason=exc.reason)
        raise HTTPException(status_code=400, detail=exc.reason) from exc

    start = time.perf_counter()
    recs, cold_start = service.recommend(user_id, top_n=top_n)
    latency_ms = (time.perf_counter() - start) * 1000

    RECOMMENDATION_REQUESTS.labels(cold_start=str(cold_start).lower()).inc()

    logger.info(
        "recommendations_served",
        user_id=user_id,
        top_n=top_n,
        cold_start=cold_start,
        result_count=len(recs),
        latency_ms=round(latency_ms, 2),
    )

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

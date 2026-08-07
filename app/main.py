from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from app.logging_config import configure_logging, get_logger
from app.model_service import RecommendationService
from app.validation import InvalidUserIdError, normalize_user_id

configure_logging()
logger = get_logger(__name__)

service: RecommendationService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service
    service = RecommendationService()
    logger.info(
        "service_ready",
        known_users=len(service.known_users),
        model_version=service.model_version,
    )
    yield


app = FastAPI(title="Personalization Service", lifespan=lifespan)

# Metricas Prometheus (request count, latencia p50/p95 via histogram, taxa de erro por status code).
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Metrica de negocio, alem das metricas tecnicas genericas acima: quantas
# recomendacoes sao servidas em fallback de cold start, por rotulo. Permite
# montar "% de requests em cold start" como sinal de produto (quantos
# usuarios novos estao recebendo recomendacao nao-personalizada), nao so
# sinal tecnico.
RECOMMENDATION_REQUESTS = Counter(
    "recommendation_requests_total",
    "Total de recomendacoes servidas, particionado por fallback de cold start",
    ["cold_start"],
)


class HealthResponse(BaseModel):
    status: str
    model_version: str
    known_users: int


class RecommendationItem(BaseModel):
    product_id: str
    score: float
    category: str
    price: float


class RecommendationsResponse(BaseModel):
    user_id: str
    cold_start: bool
    model_version: str
    recommendations: list[RecommendationItem]


@app.get("/health", response_model=HealthResponse)
def health():
    if service is None:
        raise HTTPException(status_code=503, detail="service not ready")
    return HealthResponse(
        status="ok",
        model_version=service.model_version,
        known_users=len(service.known_users),
    )


@app.get("/recommendations/{user_id}", response_model=RecommendationsResponse)
def get_recommendations(user_id: str, top_n: int = Query(default=10, ge=1, le=60)):
    if service is None:
        raise HTTPException(status_code=503, detail="service not ready")

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

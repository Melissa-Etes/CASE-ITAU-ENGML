from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from prometheus_fastapi_instrumentator import Instrumentator

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
    logger.info("service_ready", known_users=len(service.known_users))
    yield


app = FastAPI(title="Personalization Service", lifespan=lifespan)

# Metricas Prometheus (request count, latencia p50/p95 via histogram, taxa de erro por status code).
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/recommendations/{user_id}")
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

    logger.info(
        "recommendations_served",
        user_id=user_id,
        top_n=top_n,
        cold_start=cold_start,
        result_count=len(recs),
        latency_ms=round(latency_ms, 2),
    )

    return {
        "user_id": user_id,
        "cold_start": cold_start,
        "recommendations": [
            {
                "product_id": r.product_id,
                "score": r.score,
                "category": r.category,
                "price": r.price,
            }
            for r in recs
        ],
    }

"""Raiz de composicao da aplicacao (padrao MVC: aqui NAO fica logica de
negocio nem formato de resposta -- so a montagem da app e o startup).

- Model:      app/model_service.py (calculo da recomendacao) + app/validation.py
- View:       app/schemas.py (formato das respostas)
- Controller: app/routers/recommendations.py (rotas HTTP)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.logging_config import configure_logging, get_logger
from app.model_service import RecommendationService
from app.routers.recommendations import router as recommendations_router

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.service = RecommendationService()
    logger.info(
        "service_ready",
        known_users=len(app.state.service.known_users),
        model_version=app.state.service.model_version,
    )
    yield


app = FastAPI(title="Personalization Service", lifespan=lifespan)

# Metricas Prometheus (request count, latencia p50/p95 via histogram, taxa de erro por status code).
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(recommendations_router)

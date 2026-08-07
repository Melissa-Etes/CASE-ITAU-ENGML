"""Raiz de composicao da aplicacao (padrao MVC: aqui NAO fica logica de
negocio nem formato de resposta -- so a montagem da app e o startup).

- Model:      app/model_service.py (calculo da recomendacao) + app/validation.py
- View:       app/schemas.py (formato das respostas)
- Controller: app/routers/recommendations.py (rotas HTTP)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.logging_config import configure_logging, get_logger
from app.metrics import FEATURES_DATA_AGE_SECONDS
from app.model_service import RecommendationService
from app.routers.recommendations import router as recommendations_router

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = RecommendationService()
    app.state.service = service

    # set_function: o Gauge recalcula "agora - geracao do snapshot" a cada
    # scrape do Prometheus, sem precisar de thread/job de atualizacao.
    FEATURES_DATA_AGE_SECONDS.set_function(lambda: time.time() - service.features_generated_at)

    logger.info(
        "service_ready",
        known_users=len(service.known_users),
        model_version=service.model_version,
    )
    yield


app = FastAPI(title="Personalization Service", lifespan=lifespan)

# Metricas Prometheus (request count, latencia p50/p95 via histogram, taxa de erro por status code).
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(recommendations_router)

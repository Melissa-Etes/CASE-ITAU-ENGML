"""Raiz de composicao da aplicacao (padrao MVC: aqui NAO fica logica de
negocio nem formato de resposta -- so a montagem da app e o startup).

- Model:      app/service_completo.py (calculo da recomendacao) + app/validation.py
- View:       app/schemas.py (formato das respostas)
- Controller: app/routers/recommendations.py (rotas HTTP)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.logging_config import configure_logging, get_logger
from app.metrics import FEATURES_DATA_AGE_SECONDS
from app.service_completo import Recomendador
from app.routers.recommendations import router as recommendations_router
from app.schemas import ErrorResponse

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = Recomendador()
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


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Padroniza toda resposta de erro (400 de user_id invalido, 503 de
    service not ready, etc): o codigo HTTP tambem vai dentro do corpo da
    resposta (status_code), alem do header HTTP -- e a mensagem continua
    sendo exatamente a que cada camada (ex: app/validation.py) configurou.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(status_code=exc.status_code, detail=exc.detail).model_dump(),
    )

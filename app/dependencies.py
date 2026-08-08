"""Injecao de dependencia: como o Controller (routers/) obtem uma instancia
do Model (Recomendador) sem acoplar direto numa variavel global.

O service e criado uma unica vez no lifespan (app/main.py) e guardado em
app.state -- o padrao recomendado pelo proprio FastAPI para estado
compartilhado entre requests.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.service_completo import Recomendador


def get_service(request: Request) -> Recomendador:
    service: Recomendador | None = getattr(request.app.state, "service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="service not ready")
    return service

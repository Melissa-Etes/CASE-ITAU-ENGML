"""View: os formatos (contratos) de resposta da API.

Camada MVC responsavel apenas por *como o dado sai* -- nao contem logica de
negocio nem sabe como o dado foi calculado. So Model (app/service_completo.py)
sabe calcular; so o Controller (app/routers/) decide quando usar cada schema.
"""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    model_version: str
    known_users: int
    features_age_seconds: float


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


class ErrorResponse(BaseModel):
    """Formato padrao de erro: o codigo HTTP tambem vai dentro do corpo da
    resposta (status_code), nao so no header HTTP -- facilita quem consome
    a API logar/tratar o erro sem precisar inspecionar o status separado do
    corpo, e mantem a mensagem que cada camada (validation.py, etc) já
    configurou.
    """

    status_code: int
    detail: str

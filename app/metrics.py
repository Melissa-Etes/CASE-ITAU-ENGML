"""Metricas de negocio customizadas (alem das metricas tecnicas genericas do
prometheus-fastapi-instrumentator, registradas em app/main.py).
"""

from __future__ import annotations

from prometheus_client import Counter

# Quantas recomendacoes sao servidas em fallback de cold start, por rotulo.
# Permite montar "% de requests em cold start" como sinal de produto (quantos
# usuarios novos estao recebendo recomendacao nao-personalizada), nao so
# sinal tecnico.
RECOMMENDATION_REQUESTS = Counter(
    "recommendation_requests_total",
    "Total de recomendacoes servidas, particionado por fallback de cold start",
    ["cold_start"],
)

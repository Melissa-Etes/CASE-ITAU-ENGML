"""Metricas de negocio customizadas (alem das metricas tecnicas genericas do
prometheus-fastapi-instrumentator, registradas em app/main.py).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# Quantas recomendacoes sao servidas em fallback de cold start, por rotulo.
# Permite montar "% de requests em cold start" como sinal de produto (quantos
# usuarios novos estao recebendo recomendacao nao-personalizada), nao so
# sinal tecnico.
RECOMMENDATION_REQUESTS = Counter(
    "recommendation_requests_total",
    "Total de recomendacoes servidas, particionado por fallback de cold start",
    ["cold_start"],
)

# Distribuicao dos scores efetivamente retornados aos clientes (nao so a
# media). Um desvio brusco na distribuicao (ex: tudo concentrado perto de 0)
# e um sinal de alerta de qualidade do modelo antes mesmo de alguem reclamar
# -- recomendacao comum de monitoramento de ML alem das metricas tecnicas
# genericas de request/latencia/erro.
RECOMMENDATION_SCORE = Histogram(
    "recommendation_score",
    "Distribuicao dos scores de recomendacao retornados pelo modelo",
    buckets=[0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Gauge "vivo": o valor e recalculado a cada scrape via set_function (nao
# precisa de thread de atualizacao). Mede ha quanto tempo o snapshot de
# features em uso foi gerado -- relevante porque a ingestao roda em batch,
# nao em tempo real (ver SOLUTION.md).
FEATURES_DATA_AGE_SECONDS = Gauge(
    "features_data_age_seconds",
    "Idade em segundos do snapshot de features pre-computadas em uso",
)

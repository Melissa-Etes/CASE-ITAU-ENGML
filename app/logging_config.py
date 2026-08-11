"""Logging JSON estruturado (stdout), pronto para ser coletado por um agente
(ex: CloudWatch Logs driver `awslogs` no ECS) sem configuracao extra.
"""

from __future__ import annotations

import logging
import sys

import structlog


# Configura o pipeline de log da aplicacao inteira: cada log passa pela
# lista de processors em sequencia (adiciona timestamp, nivel, e por fim
# serializa tudo como JSON) antes de ir para o stdout.
def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Cria um logger identificado pelo nome do modulo que o chamou -- esse
# nome aparece em cada linha de log gerada a partir dali.
def get_logger(name: str):
    return structlog.get_logger(name)

"""Validacao e normalizacao do user_id vindo da URL.

Formato observado nos dados: `u_` + 4 digitos (ex: u_0231). Fazemos a
validacao aqui, na borda do sistema (antes de tocar no service/modelo),
para distinguir dois casos bem diferentes:

- user_id malformado (typo, caracteres invalidos, tamanho absurdo) -> erro
  400, o cliente mandou algo errado.
- user_id com formato valido mas que nao existe no historico -> cold start
  (200, fallback), o cliente mandou algo certo, so nao temos dado dele.

Misturar os dois faria todo lixo de input cair silenciosamente em cold
start, escondendo bugs de integracao no lado do consumidor da API.
"""

from __future__ import annotations

import re

USER_ID_MAX_LENGTH = 32  # generoso o suficiente; corta input absurdo antes do regex
USER_ID_PATTERN = re.compile(r"^u_\d{4}$")


class InvalidUserIdError(ValueError):
    def __init__(self, user_id: str, reason: str) -> None:
        self.user_id = user_id
        self.reason = reason
        super().__init__(reason)


def normalize_user_id(raw_user_id: str) -> str:
    """Normaliza (trim + lowercase) e valida o formato do user_id.

    Levanta InvalidUserIdError se o input nao puder ser um user_id valido,
    independente de existir ou nao no historico de eventos.
    """
    candidate = raw_user_id.strip()

    if not candidate:
        raise InvalidUserIdError(raw_user_id, "user_id nao pode ser vazio")

    if len(candidate) > USER_ID_MAX_LENGTH:
        raise InvalidUserIdError(raw_user_id, f"user_id excede o tamanho maximo de {USER_ID_MAX_LENGTH} caracteres")

    candidate = candidate.lower()

    if not USER_ID_PATTERN.match(candidate):
        raise InvalidUserIdError(raw_user_id, "user_id deve seguir o formato 'u_' + 4 digitos (ex: u_0231)")

    return candidate

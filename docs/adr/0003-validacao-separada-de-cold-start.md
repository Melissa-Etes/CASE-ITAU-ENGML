# 0003 — Validação de formato do `user_id` separada da lógica de cold start

Status: Aceita

## Contexto

Existem dois casos bem diferentes que um `user_id` "não encontrado" poderia representar: um
formato inválido (typo, caractere estranho, string vazia — erro do cliente) e um formato válido
que simplesmente não existe no histórico ainda (usuário novo legítimo). Tratar os dois igual
faria qualquer lixo de input cair silenciosamente em cold start, escondendo bugs de integração do
lado de quem consome a API.

## Decisão

`app/validation.py::normalize_user_id` valida o formato (`u_` + 4 dígitos, normalizando
maiúscula/espaço) **antes** de qualquer lógica de negócio, na borda da API
(`app/routers/recommendations.py`, antes de chamar `Recomendador`). Formato inválido → `400 Bad
Request`. Formato válido mas desconhecido → `200 OK` com cold start.

Importante: essa camada só existe na API — `Recomendador.recommend()` sozinho (usado direto, sem
passar pela validação) **não** distingue os dois casos, trata qualquer `user_id` desconhecido
como cold start (documentado em
`tests/test_service_completo.py::test_recommend_com_lixo_tambem_cai_em_cold_start_sem_erro`).

## Consequências

- Cliente recebe sinal claro de "você mandou algo errado" vs. "seu usuário é novo, sem problema".
- Camada de validação é reutilizável e testável isoladamente (`tests/test_validation.py`), sem
  precisar carregar modelo/dados.
- Trade-off: se alguém chamar `Recomendador.recommend()` fora do caminho da API (ex: um script,
  um notebook), não terá essa proteção — precisa validar manualmente antes.

# 0004 — FastAPI com endpoint síncrono (`def`, não `async def`)

Status: Aceita

## Contexto

FastAPI suporta handlers síncronos e assíncronos. O endpoint principal
(`GET /recommendations/{user_id}`) faz só lookup em memória, `scaler.transform` e
`model.predict_proba` — nenhuma chamada de rede real (sem banco externo, sem outra API).

## Decisão

`app/routers/recommendations.py::get_recommendations` é `def` síncrono, não `async def`. FastAPI
já executa handlers síncronos num threadpool interno, então múltiplos requests continuam sendo
atendidos em paralelo sem precisar de `await`.

## Consequências

- Código mais simples, sem contaminar toda a cadeia de chamadas com `async`/`await`
  desnecessariamente.
- `async def` só compensaria se o handler fizesse alguma chamada de rede real (ex: banco via
  driver assíncrono) — não é o caso aqui.
- Trade-off descoberto via teste de carga (`locustfile.py`): o throughput satura em ~180-190
  req/s, característico de saturação do threadpool (não do event loop). A correção conhecida
  (múltiplos workers Uvicorn) não foi validada dentro do prazo do case — ver
  `docs/ROUTING.md` → "Investigar lentidão/gargalo".

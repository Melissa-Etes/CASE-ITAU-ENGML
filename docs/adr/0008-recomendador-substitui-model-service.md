# 0008 — `Recomendador` (app/service_completo.py) substitui `app/model_service.py` como Model

Status: Aceita

## Contexto

O `RecommendationService` original (`app/model_service.py`) foi a implementação entregue como
parte do case. Em paralelo, uma reimplementação própria (`Recomendador`) foi construída do zero
como exercício — separando a lógica pura de negócio (`app/recomendador/`: `is_known_user`,
`montar_candidatos`, `ordenar_candidatos_por_score`, `scores`) de uma classe que carrega e guarda
estado (`Recomendador`, em `app/service_completo.py`).

## Decisão

`app/model_service.py` foi removido do projeto. `Recomendador` passou a ser o único Model,
plugado em `app/dependencies.py` e `app/main.py` no lugar do `RecommendationService` original.
Para isso, `Recomendador` foi projetado com **interface idêntica** à original:

- `recommend(user_id, top_n)` devolve `(list[Recommendation], cold_start: bool)`.
- Atributos `model_version`, `known_users`, `features_generated_at`.
- Mesmo fail-fast de integridade do artefato (`ModelIntegrityError` se o `scaler` não bater com
  `feature_cols`).
- `Recommendation` (dataclass) e `ModelIntegrityError` agora são definidos dentro de
  `service_completo.py`, não importados de `model_service.py` (desacoplamento total).

## Consequências

- Por manter o mesmo contrato, trocar a implementação em `app/dependencies.py`/`app/main.py` não
  exigiu **nenhuma** mudança em `app/routers/recommendations.py`, `app/schemas.py`, no scrape do
  Prometheus, nem no dashboard do Grafana — todas essas camadas dependem só do contrato, não de
  como o cálculo é feito por dentro.
- `tests/test_model_service.py` (que testava o `model_service.py` original) foi removido junto —
  a cobertura equivalente agora está em `tests/test_service_completo.py`,
  `tests/test_user_check.py`, `tests/test_recommend.py`, `tests/test_score.py`, e
  `tests/test_model_quality_gate.py`.
- Trade-off: qualquer documentação (README, comentários antigos) que ainda mencione
  `app/model_service.py` está desatualizada e precisa de correção — ver `AGENTS.md` para o
  apontamento atual dos arquivos-chave.

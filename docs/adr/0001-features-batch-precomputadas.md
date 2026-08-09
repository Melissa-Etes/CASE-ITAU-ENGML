# 0001 — Features pré-computadas em batch, não calculadas em request-time

Status: Aceita

## Contexto

O modelo precisa de 5 features por par usuário-produto (`interactions`, `price`, `avg_rating`,
`popularity_score`, `user_affinity_match`). Duas delas (`interactions`, `user_affinity_match`)
exigem agregar todo o histórico de `events.csv` por usuário — uma operação de `groupby`/`join`
não trivial. O dado recebido é um snapshot histórico, não um stream em tempo real.

## Decisão

`ingestion/build_features.py` roda como job offline (dentro do build da imagem Docker) e gera
`data/processed/user_product_features.parquet` com a matriz completa já calculada. A API
(`app/service_completo.py`) só **lê** esse parquet no startup — nunca recalcula nada por request.

## Consequências

- Request HTTP fica rápido: é só lookup em memória + `predict_proba`, sem `groupby` por request.
- A lógica de feature engineering fica isolada e testável sem I/O (`tests/test_features.py`).
- Trade-off aceito: atualizar os dados exige rodar o job de novo (ou rebuildar a imagem) —
  não há atualização em tempo real. Um usuário que começa a interagir agora continua em cold
  start até o próximo ciclo de ingestão.
- Ver `docs/ROUTING.md` → "Mudar a frequência de atualização dos dados".

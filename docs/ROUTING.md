# Codebase map / routing table

"Quero mudar X" → vá em Y → cuidado com Z. Cada linha aponta pro arquivo certo e, quando existe,
pro ADR que explica a decisão que você provavelmente vai esbarrar.

| Quero... | Vá em | Cuidado / decisão relacionada |
|---|---|---|
| Mudar o formato aceito de `user_id` | `app/validation.py` (`USER_ID_PATTERN`) | Atualize também `tests/test_validation.py` e `tests/test_data_quality.py::test_products_...`/`test_events_...` se o dado real também mudar de formato. |
| Adicionar uma feature nova ao modelo | `ingestion/features.py` (`build_feature_matrix`) **e** re-treinar o modelo (fora de escopo — ver `model/model_card.json`) | `feature_cols` vem do `model.pkl`, não é escolhido pelo código da API — mudar `features.py` sem trocar o modelo quebra `test_scaler_foi_ajustado_para_mesma_quantidade_de_feature_cols` em `tests/test_service_completo.py`. |
| Mudar a lógica de ranking (como os candidatos são pontuados/ordenados) | `app/recomendador/recommend.py` (`ordenar_candidatos_por_score`) e `app/recomendador/score.py` (`scores`) | [ADR 0002](adr/0002-cold-start-caminho-unico.md) — ranking de cold start e usuário conhecido convergem no mesmo `scores()`, não duplique lógica. |
| Mudar o comportamento de cold start (usuário sem histórico) | `app/recomendador/recommend.py` (`montar_candidatos`, branch `if user_id not in known_users`) | [ADR 0002](adr/0002-cold-start-caminho-unico.md). |
| Adicionar um endpoint novo | `app/routers/recommendations.py` (novo `@router.get`/`.post`) + registrar em `app/main.py` se for um router novo | Endpoints de leitura são `GET` síncrono — ver [ADR 0004](adr/0004-fastapi-sync-endpoint.md) antes de decidir `async def`. |
| Mudar o formato de resposta da API | `app/schemas.py` | Atualize `tests/test_api.py` — o schema é o contrato público, mudança quebra clientes existentes. |
| Adicionar/mudar um log estruturado | `app/routers/recommendations.py` (chamadas a `logger.info`/`logger.warning`) e `app/logging_config.py` (formato) | Logs são JSON — não misture `print()`. |
| Adicionar uma métrica Prometheus nova | `app/metrics.py` (novo `Counter`/`Histogram`/`Gauge`) | Registre o `.observe()`/`.inc()` no ponto certo do fluxo (`routers/recommendations.py` ou `main.py`); atualize o dashboard em `observability/grafana/provisioning/dashboards/personalization-service.json` se quiser visualizar. |
| Trocar o modelo/artefato (`model.pkl`) | `model/model.pkl` + `model/model_card.json` | Rode `python scripts/compute_score_baseline.py` de novo e recalibre os limites em `tests/test_model_quality_gate.py` — o baseline atual é específico do modelo atual. |
| Mudar a frequência de atualização dos dados | `ingestion/build_features.py` (hoje roda só no build da imagem Docker) | [ADR 0001](adr/0001-features-batch-precomputadas.md) — trade-off consciente de simplicidade vs. atualização em tempo real. |
| Adicionar autenticação/rate limiting | Não existe hoje — entraria como middleware em `app/main.py` ou dependency em `app/dependencies.py` | Gap conhecido, ver `AGENTS.md`. Nenhum ADR existe ainda porque nunca foi implementado — ao implementar, escreva um. |
| Investigar lentidão/gargalo | `locustfile.py` (teste de carga) + [SOLUTION.md, seção "Teste de performance"](../SOLUTION.md) | Achado conhecido: throughput satura em ~180-190 req/s por saturação do threadpool do Uvicorn — correção sugerida (`--workers N`) não validada ainda. |
| Mudar a estratégia de deploy (hoje é recriar o container) | `docker-compose.yml`, `.github/workflows/ci.yml` | Nenhuma estratégia de zero-downtime implementada — gap conhecido, ver `AGENTS.md`. |
| Adicionar um teste de qualidade de dado novo | `tests/test_data_quality.py` | Roda contra `data/events.csv`/`data/products.csv` **reais**, não sintéticos — diferente de `tests/test_features.py`. |
| Adicionar um teste de lógica de feature engineering | `tests/test_features.py` | Usa dado sintético, testa a função, não o arquivo real — diferente de `test_data_quality.py`. |
| Recalibrar o gate de qualidade do modelo | `scripts/compute_score_baseline.py` (rode) → `tests/test_model_quality_gate.py` (atualize os limites) | Necessário sempre que o `model.pkl` ou o snapshot de features mudar de forma legítima. |
| Adicionar uma função pura nova ao pacote `recomendador` | `app/recomendador/<novo_arquivo>.py` + reexportar em `app/recomendador/__init__.py` | Siga o padrão existente: função recebe tudo como parâmetro explícito, não acessa estado global nem `self`. |
| Mudar como o CI builda/testa | `.github/workflows/ci.yml` | A imagem é taggeada por `${{ github.sha }}` — ver [ADR 0007](adr/0007-ci-sem-cd.md). |
| Entender por que `Recomendador` existe em vez do `model_service.py` antigo | — | [ADR 0008](adr/0008-recomendador-substitui-model-service.md) — `model_service.py` foi removido, `service_completo.py` é o Model atual. |

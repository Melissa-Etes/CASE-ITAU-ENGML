# SOLUTION.md

Entrega do case (personalization service em FastAPI, servindo um modelo de propensão de compra
**já treinado**). O foco pedido pelo [README](README.md) é 100% engenharia — ingestão de dados,
API, tratamento de edge cases, testes e observabilidade — não treino ou melhoria do modelo. Este
documento cobre a narrativa de decisões e trade-offs; para outras necessidades, ver a documentação
complementar:

| Preciso de... | Vá em |
|---|---|
| Comandos do dia a dia (subir, testar, URLs) | [`SOLUTION_ATUAL.md`](SOLUTION_ATUAL.md) |
| O porquê de cada decisão, em formato curto e consultável | [`docs/adr/`](docs/adr/) |
| Onde mexer para um tipo de mudança específico | [`docs/ROUTING.md`](docs/ROUTING.md) |
| Visão geral de navegação (humano + IA) | [`AGENTS.md`](AGENTS.md) |

---

## O que foi pedido vs. o que foi entregue

| Pedido pelo case | Entregue |
|---|---|
| Servir o modelo já treinado via API | `GET /recommendations/{user_id}` (FastAPI), ranking por score do modelo |
| Tratar edge cases (usuário sem histórico) | Cold start no mesmo caminho de scoring (ADR 0002) |
| Testes | 59 funções de teste / 67 casos, incluindo integração real sem mock, qualidade de dado e gate de qualidade de modelo |
| Observabilidade | Logs estruturados (JSON) + métricas Prometheus + dashboard Grafana provisionado |
| Documentação de decisões | Este arquivo + `docs/adr/` (8 registros formais) |

---

## Arquitetura, em uma frase por camada

Padrão MVC: **Model** = `app/service_completo.py` (classe `Recomendador`, delega lógica pura para
`app/recomendador/`) · **View** = `app/schemas.py` · **Controller** = `app/routers/recommendations.py`
· **Composição** = `app/main.py`. Ver diagrama do ciclo de vida de uma requisição em
[`AGENTS.md`](AGENTS.md).

---

## Decisões de arquitetura e trade-offs

Resumo narrativo — o porquê completo de cada uma, com consequências detalhadas, está no ADR
correspondente.

### Dados

**Features pré-computadas em batch**, não calculadas por request. `ingestion/build_features.py`
roda offline (no build da imagem Docker), gera um parquet com a matriz completa
`user_id × product_id`; a API só lê. Trade-off aceito: atualizar dados exige rodar o job de novo,
sem tempo real. → [ADR 0001](docs/adr/0001-features-batch-precomputadas.md)

**`user_affinity_match`** é derivado juntando `events.csv` + `products.csv`, contando interações
por categoria e escolhendo a de maior contagem (desempate por popularidade média, depois ordem
alfabética — determinístico). `interactions` conta todo `event_type` igualmente, mantendo a lógica
simples e alinhada à definição de referência do `model_card.json`.

### Modelo servido

**Cold start unificado**: usuário sem histórico é tratado como neutro
(`interactions=0`, `user_affinity_match=0`) para todo o catálogo, e pontuado pela **mesma** função
de scoring do usuário conhecido — sem duplicar lógica de ranking em dois caminhos que poderiam
divergir. → [ADR 0002](docs/adr/0002-cold-start-caminho-unico.md)

**Validação de input separada de cold start**: `user_id` malformado → `400`; formato válido mas
desconhecido → `200` com cold start. Evita que lixo de input vire silenciosamente uma resposta
"válida" genérica. → [ADR 0003](docs/adr/0003-validacao-separada-de-cold-start.md)

### API e infraestrutura

**FastAPI, endpoint síncrono** (`def`, não `async def`) — o handler só faz lookup em memória e
`predict_proba`, sem I/O de rede; FastAPI já roda handlers síncronos em threadpool.
→ [ADR 0004](docs/adr/0004-fastapi-sync-endpoint.md)

**Três containers separados** (API, Prometheus, Grafana) via `docker-compose.yml`, em vez de uma
imagem única — cada serviço com ciclo de vida próprio, reaproveitando imagens oficiais já
mantidas. → [ADR 0005](docs/adr/0005-containers-separados.md)

**Sem mock no teste de integração** — sobe a aplicação real (modelo, scaler, dados) via
`TestClient`, de propósito, para provar que as peças se encaixam de verdade.
→ [ADR 0006](docs/adr/0006-sem-mock-testes-integracao.md)

**CI automatizado, sem CD**: cada push roda ingestão + suíte de testes completa + build da imagem
(taggeada por commit) + healthcheck + scan de vulnerabilidade (Trivy). Sem deploy automático —
não há alvo de infraestrutura real provisionado para publicar. → [ADR 0007](docs/adr/0007-ci-sem-cd.md)

**`Recomendador` (`app/service_completo.py`) é o Model atual**, substituindo a implementação
original (`app/model_service.py`, removida) por uma reimplementação com interface idêntica —
troca feita sem alterar nenhuma linha do Controller, View, métricas ou dashboard, porque as duas
implementações respeitam o mesmo contrato. → [ADR 0008](docs/adr/0008-recomendador-substitui-model-service.md)

---

## Testes

59 funções de teste, 67 casos executados (`python -m pytest -v`, sem path especial — coleta tudo
em `tests/`), cobrindo 4 categorias:

1. **Lógica** (dado sintético, sem I/O): feature engineering, funções puras de `app/recomendador/`.
2. **Integração real** (sem mock): `TestClient` sobe a API inteira; casos de usuário conhecido,
   cold start, validação de `top_n`, normalização de `user_id`, rejeição de formato inválido
   (incluindo tentativas de SQL injection/XSS), métricas expostas.
3. **Qualidade dos dados reais** (`tests/test_data_quality.py`): valida `events.csv`/`products.csv`
   de verdade — schema, nulos, ranges plausíveis, referências entre arquivos íntegras. Distinto dos
   testes de lógica: pega dado corrompido, não bug de código.
4. **Gate de qualidade do modelo** (`tests/test_model_quality_gate.py`): compara a distribuição de
   score do modelo carregado contra um baseline calibrado
   (`scripts/compute_score_baseline.py`) — falha o CI se o score saturar ou desviar do esperado,
   antes de qualquer coisa chegar em produção.

Detalhe arquivo-por-arquivo em [`SOLUTION_ATUAL.md`](SOLUTION_ATUAL.md#testes).

---

## O que eu loga/meço hoje

- Log estruturado JSON (`structlog`) por request: `user_id`, `latency_ms`, `cold_start`.
- Aviso (`invalid_user_id`) para toda tentativa de request malformado.
- `/metrics` (Prometheus): contagem de requests por rota/status, histograma de latência (p50/p95).
- Métrica de negócio `recommendation_requests_total{cold_start=...}` — taxa de cold start como
  sinal de produto, não só técnico.
- **Distribuição de score servido** (`recommendation_score`, Histogram) — desvio brusco é alerta de
  qualidade do modelo antes de alguém reclamar.
- **Idade do snapshot de features** (`features_data_age_seconds`, Gauge recalculado a cada scrape)
  — relevante porque a ingestão é batch, não tempo real.
- `HEALTHCHECK` no Dockerfile, dashboard Grafana provisionado automaticamente via
  `docker-compose.yml` (Prometheus faz scrape a cada 5s).

**Adicionaria com mais tempo:** alertas configurados sobre os thresholds do dashboard; tracing
distribuído (só relevante se este serviço passar a chamar outros); detecção formal de data drift
(comparar distribuição de produção contra distribuição de treino — hoje só monitoro a distribuição
de *output*, não comparo contra uma referência de treino).

---

## O que eu faria diferente com mais tempo

- **Ingestão incremental** — cold start se resolveria sozinho conforme o usuário interage, em vez
  de depender de novo build/deploy.
- **Ponderar `user_affinity_match` por tipo de evento e recência**, usando `event_type`/`timestamp`
  (já existem no dado bruto, não explorados hoje).
- **Separar artefato de dados do build da imagem** — publicar o parquet versionado externamente,
  API busca a versão mais recente no startup.
- **Escalar além de um processo único** — o teste de carga (abaixo) achou saturação por
  threadpool; validar `uvicorn --workers N` dentro do Docker/Linux (não testado no prazo do case,
  por limitação do ambiente onde rodei o teste — Windows nativo).
- **Filtro de produtos já comprados** no ranking — hoje o modelo pode recomendar algo que o usuário
  já adquiriu.
- **Autenticação e rate limiting** — gap consciente, fora do escopo definido pelo case
  (engenharia de serving), mas real para produção.

---

## Teste de performance / carga

Teste de carga real (`locustfile.py`) contra a API via `docker-compose`, simulando usuários
simultâneos batendo em `/recommendations/{user_id}` (mix conhecido/cold start) e `/health`.

```bash
pip install locust
locust -f locustfile.py --host http://localhost:8000 --headless --users 150 --spawn-rate 50 --run-time 20s
```

| Usuários simultâneos | Throughput | p95 | Taxa de erro |
|---|---|---|---|
| 10 | 49 req/s | 37 ms | 0% |
| 50 | 186 req/s | 200 ms | 0% |
| 150 | 184 req/s | 870 ms | 0% |
| 300 | 164 req/s | 2.200 ms | 0% |

**Achado:** throughput satura em **~180-190 req/s** independente da concorrência — sinal de
saturação do threadpool interno do Uvicorn (endpoint síncrono ocupa uma das ~40 threads padrão
por request; acima disso, fila cresce, latência sobe quase linear, mas **zero erros** em qualquer
nível testado — degradação é só de latência, não de disponibilidade).

**Causa raiz e correção conhecida:** um processo Uvicorn usa efetivamente 1 núcleo de CPU (GIL)
para código Python. Correção padrão: múltiplos workers (`uvicorn --workers N`) atrás de um load
balancer. **Não validada** — `--workers` usa multiprocessing, instável no Windows nativo (ambiente
onde rodei o teste); funcionaria normalmente dentro do container Linux/CI, mas não coube repetir
o comparativo no prazo do case.

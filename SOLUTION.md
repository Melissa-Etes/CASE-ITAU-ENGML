# SOLUTION.md

Entrega do case Personalization Service. O foco pedido é 100% engenharia — arquitetura, API,
tratamento de dados, qualidade de código e decisões de produção — não treino ou melhoria do
modelo. Este documento segue a estrutura dos 6 itens do enunciado. Documentação complementar,
para não sobrecarregar este arquivo:

| Preciso de... | Vá em |
|---|---|
| O porquê de cada decisão, em formato curto e consultável | [`docs/adr/`](docs/adr/) |
| Onde mexer para um tipo de mudança específico | [`docs/ROUTING.md`](docs/ROUTING.md) |
| Visão geral de navegação (humano + IA) | [`AGENTS.md`](AGENTS.md) |

---

## Como rodar

### Docker (recomendado)

```bash
docker compose up -d --build   # sobe API + Prometheus + Grafana
docker compose logs -f         # acompanhar logs
docker compose down            # desligar tudo
```

`http://localhost:8000/docs` (Swagger) · `http://localhost:8000/health` ·
`http://localhost:3000/d/personalization-service` (Grafana, sem login).

Só a API, sem a stack de observabilidade:
```bash
docker build -t personalization-service .
docker run -d --name pers -p 8000:8000 personalization-service
```

### Local, sem Docker (Python 3.12+)

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m ingestion.build_features   # gera data/processed/user_product_features.parquet
uvicorn app.main:app --reload
```

### Testes

```bash
python -m pytest -v
```

### Teste de carga

```bash
pip install locust
locust -f locustfile.py --host http://localhost:8000 --headless --users 150 --spawn-rate 50 --run-time 20s
```

---

## 1. Ingestão / preparo de dados

`ingestion/build_features.py` roda como **job offline**, antes da API subir (hoje: dentro do
`docker build` da imagem). Lê `events.csv` + `products.csv`, calcula as 5 features esperadas pelo
modelo (`ingestion/features.py`) e grava `data/processed/user_product_features.parquet` — uma
matriz completa `user_id × product_id`. A API só **lê** esse parquet no startup, nunca recalcula
por request.

**`user_affinity_match`** (a única feature não pronta em nenhum CSV) é derivada assim: para cada
usuário, conta interações por categoria (join `events.csv` + `products.csv` por `product_id`) e
escolhe a categoria de maior contagem como "afinidade" — seguindo a definição de referência do
`model_card.json`. Critério de desempate (não especificado pelo case, documentado aqui como pedido):
maior `popularity_score` médio entre as categorias empatadas; se ainda empatar, ordem alfabética —
garante resultado determinístico.

**Por que job offline, e não calcular em request-time:** o dado é um snapshot histórico, não um
stream em tempo real; calcular `interactions`/`user_affinity_match` por request exigiria `groupby`
sobre `events.csv` inteiro a cada chamada — desnecessário e lento. Trade-off aceito: atualizar
dados exige rodar o job de novo (ou rebuildar a imagem). Detalhes e alternativa considerada:
[ADR 0001](docs/adr/0001-features-batch-precomputadas.md).

---

## 2. Endpoint de recomendação

`GET /recommendations/{user_id}?top_n=10` (padrão 10, aceita 1–60) devolve uma lista ranqueada por
`score` do modelo (`app/routers/recommendations.py` → `app/service_completo.py`). Cada item:
`product_id`, `score`, `category`, `price`. `GET /health` expõe status, versão do modelo, nº de
usuários conhecidos e idade dos dados.

**Ranking:** score = `model.predict_proba(scaler.transform(X))[:, 1]` (probabilidade da classe
positiva), ordenado decrescente, cortado em `top_n` — o score do modelo é literalmente a base da
ordenação, sem re-ranqueamento por regra de negócio por cima.

---

## 3. Cold start

Quando `user_id` não existe no histórico, o serviço trata o usuário como **neutro**
(`interactions=0`, `user_affinity_match=0`) para todo o catálogo, e pontua com a **mesma** função
de scoring do usuário conhecido — na prática, o ranking converge para "produtos mais
populares/bem avaliados" (únicas features que ainda diferenciam as linhas: `price`, `avg_rating`,
`popularity_score`). Sem duplicar lógica de ranking em dois caminhos de código.
Detalhes: [ADR 0002](docs/adr/0002-cold-start-caminho-unico.md).

**Validação separada de cold start:** `user_id` com formato inválido (`app/validation.py`) →
`400`, **antes** de qualquer lógica de negócio. `user_id` bem formado mas desconhecido → `200` com
cold start. Misturar os dois esconderia bug de integração do lado do cliente atrás de uma resposta
"válida" genérica. [ADR 0003](docs/adr/0003-validacao-separada-de-cold-start.md).

---

## 4. Testes

59 funções de teste, 67 casos executados (`pytest -v`, sem path restrito — coleta tudo em
`tests/`):

- **Unitários de feature engineering** (`test_features.py`) — dado sintético em memória, sem I/O.
- **Unitários das peças do serving** (`test_user_check.py`, `test_recommend.py`, `test_score.py`)
  — cada função pura (`is_known_user`, `montar_candidatos`, `ordenar_candidatos_por_score`,
  `scores`) testada isolada.
- **Endpoint principal + cold start** (`test_service_completo.py`, `test_api.py`) — usuário
  conhecido ranqueado por score, cold start sem erro, `top_n` validado, normalização de
  maiúscula, rejeição de formato inválido.
- **Integração real, sem mock**: `test_api.py` sobe a aplicação inteira via `TestClient` do
  FastAPI — modelo, scaler e dados reais, request HTTP até resposta, nenhuma camada mockada
  (justificativa: [ADR 0006](docs/adr/0006-sem-mock-testes-integracao.md)).
- **Qualidade dos dados reais** (`test_data_quality.py`) — schema/ranges de `events.csv`/
  `products.csv` de verdade, distinto de testar a lógica com dado sintético.
- **Gate de qualidade do modelo** (`test_model_quality_gate.py`) — compara a distribuição de score
  do modelo carregado contra um baseline calibrado; falha o CI se saturar ou desviar.

---

## 5. Observabilidade

### Logs

JSON estruturado (`structlog`) em todo request principal: `user_id`, `latency_ms` (medida em
torno da chamada ao serviço), `cold_start` — os três campos pedidos explicitamente pelo case.
Log de aviso (`invalid_user_id`) para `user_id` malformado.

### Métricas

`/metrics` em formato Prometheus (bônus implementado), via `prometheus-fastapi-instrumentator`
(contagem de requests por rota/status, histograma de latência) + métricas de negócio próprias
(`app/metrics.py`): `recommendation_requests_total{cold_start=...}`, `recommendation_score`
(Histogram), `features_data_age_seconds` (Gauge).

### Grafana: dashboard e por que cada gráfico foi escolhido

Provisionado automaticamente via `docker-compose.yml` (sem configuração manual) — Prometheus faz
scrape de `/metrics` a cada 5s, Grafana já sobe com datasource e dashboard prontos em
`observability/`. 8 painéis, cada um respondendo a uma pergunta operacional específica, não
"gráficos genéricos":

| Painel | Pergunta que responde |
|---|---|
| **Requests/s por status** | O tráfego está normal, ou tem um pico/queda anormal de volume? |
| **Latência p50/p95** | A experiência típica está boa (p50), e o pior caso "normal" também (p95)? |
| **Taxa de erro (5xx)** | Quantos requests estão de fato falhando agora? |
| **Taxa de cold start** | Que fração dos usuários está recebendo recomendação não-personalizada — sinal de *produto* (quantos usuários novos chegam), não só técnico. |
| **Recomendações: cold start vs. conhecido** | Volume absoluto dos dois caminhos ao longo do tempo — útil pra ver se um pico de cold start é sazonal ou anômalo. |
| **Distribuição de score (heatmap)** | Não só a média — a forma inteira da distribuição. Um colapso repentino (tudo virando perto de 0) é sinal de alerta de qualidade do modelo antes de qualquer reclamação de usuário. |
| **Idade do snapshot de features** | Há quanto tempo os dados não são atualizados — relevante porque a ingestão é batch (item 1); thresholds em amarelo (1 dia) e vermelho (7 dias) sinalizam job de reingestão parado. |
| **Score médio + Score p50/p90** | Vão além do genérico "olhe o gráfico": o painel de score médio tem faixa verde calibrada **nos dois sentidos** em torno de um baseline calculado empiricamente (`scripts/compute_score_baseline.py`) — desvio pra baixo (modelo "zerado") *e* pra cima (saturação/vazamento de feature) são os dois sinais de alerta, não só queda. O painel de percentis (p50/p90) é mais confiável que a média sozinha para detectar um desvio de distribuição real, porque não se deixa "mascarar" por outliers. |

**Por que calibrar thresholds com um baseline calculado, em vez de valores redondos "no chute":**
rodei o modelo real sobre o snapshot de features real (`scripts/compute_score_baseline.py`),
medindo a distribuição do top-10 score efetivamente servido por usuário (média 0,110, mediana
0,089, p10 0,070, p90 0,184) — e usei esse número real pra desenhar a faixa verde do painel
"Score médio", em vez de um limite arbitrário. O mesmo baseline também virou gate automatizado no
CI (`tests/test_model_quality_gate.py`), não só visual no dashboard.

**Adicionaria com mais tempo:** alertas configurados sobre esses thresholds (hoje os painéis
mostram, mas nada dispara notificação automaticamente); tracing distribuído (só relevante se este
serviço passar a chamar outros); detecção formal de data drift (comparação estatística contra a
distribuição de treino, não só contra um baseline de produção).

---

## 6. Documentação

Este arquivo (como rodar, decisões e trade-offs) + [`docs/adr/`](docs/adr/) (8 registros formais,
um por decisão) + [`AGENTS.md`](AGENTS.md) (navegação) + [`docs/ROUTING.md`](docs/ROUTING.md)
(onde mexer para cada tipo de mudança).

### Decisões de arquitetura e trade-offs (resumo — detalhe completo em cada ADR)

- **FastAPI, endpoint síncrono** (`def`, não `async def`) — trabalho é CPU puro (scaler +
  predict_proba), sem I/O de rede; FastAPI já roda `def` em threadpool, paralelizando sem
  `async`/`await` desnecessário. [ADR 0004](docs/adr/0004-fastapi-sync-endpoint.md).
- **3 containers separados** (API, Prometheus, Grafana) via `docker-compose.yml` — cada um com
  ciclo de vida próprio, reaproveitando imagens oficiais já mantidas.
  [ADR 0005](docs/adr/0005-containers-separados.md).
- **`Recomendador`** (`app/service_completo.py`) é o Model atual, com interface deliberadamente
  estável (`recommend()` devolve `(recomendações, cold_start)`, mesmos atributos de
  versão/dados) — permite trocar a implementação interna sem tocar em Controller, View, métricas
  ou dashboard. [ADR 0008](docs/adr/0008-recomendador-substitui-model-service.md).
- **CI automatizado, sem CD**: cada push roda ingestão + suíte completa (incluindo os 2 gates de
  qualidade) + build com imagem versionada por commit + healthcheck + scan Trivy. Sem deploy
  automático — não há alvo de infraestrutura real provisionado.
  [ADR 0007](docs/adr/0007-ci-sem-cd.md).

### O que faria diferente com mais tempo

- **Ingestão incremental** — cold start se resolveria sozinho conforme o usuário interage, sem
  depender de novo build/deploy.
- **Ponderar `user_affinity_match` por tipo de evento e recência**, usando `event_type`/
  `timestamp` (já existem no dado bruto, não explorados hoje).
- **Separar artefato de dados do build da imagem** — parquet versionado publicado externamente,
  API busca a versão mais recente no startup.
- **Validar múltiplos workers Uvicorn** — teste de carga achou saturação de throughput
  (~180-190 req/s) por threadpool; a correção padrão (`--workers N`) não foi validada por
  limitação do ambiente onde rodei o teste (Windows nativo — multiprocessing do Uvicorn é
  instável fora de Linux).
- **Filtro de produtos já comprados** no ranking.
- **Autenticação e rate limiting** na API — gap consciente, fora do escopo definido pelo case.

---

## Requisitos técnicos

Python 3.12 · FastAPI · Docker (`Dockerfile` multi-stage + `docker-compose.yml`) · sem banco de
dados real (parquet em memória, processado offline).

---

## Teste de performance / carga

Teste de carga real (`locustfile.py`) contra a API via `docker-compose`.

```bash
locust -f locustfile.py --host http://localhost:8000 --headless --users 150 --spawn-rate 50 --run-time 20s
```

| Usuários simultâneos | Throughput | p95 | Taxa de erro |
|---|---|---|---|
| 10 | 49 req/s | 37 ms | 0% |
| 50 | 186 req/s | 200 ms | 0% |
| 150 | 184 req/s | 870 ms | 0% |
| 300 | 164 req/s | 2.200 ms | 0% |

**Achado:** throughput satura em ~180-190 req/s independente da concorrência — saturação do
threadpool do Uvicorn, não do event loop (0% de erro em todos os níveis — degradação é só de
latência). Correção conhecida (`uvicorn --workers N`) não validada, ver "o que faria diferente".

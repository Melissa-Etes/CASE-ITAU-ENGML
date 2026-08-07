# SOLUTION.md

## Como rodar o projeto

### Local (Python 3.12+)

```bash
pip install -r requirements.txt
python -m ingestion.build_features   # gera data/processed/user_product_features.parquet
uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000`. Documentação interativa (Swagger) em `http://localhost:8000/docs`.

### Testes

```bash
pytest -v
```

26 testes: unitários de feature engineering (dado sintético, sem I/O), unitários de validação de
input, testes do endpoint principal (usuário conhecido, cold start, validação de `top_n`), e um
teste de integração via `TestClient` do FastAPI que sobe a aplicação real inteira — modelo, scaler
e dados de verdade — sem mockar nenhuma camada interna.

### Docker

```bash
docker build -t personalization-service .
docker run -d --name pers -p 8000:8000 personalization-service
docker ps          # confirma STATUS: healthy
curl http://localhost:8000/health
curl http://localhost:8000/recommendations/u_0231
```

O job de ingestão (`ingestion/build_features.py`) roda **dentro do build da imagem** — o container
já sobe com o parquet de features pronto, sem depender de nada externo no startup.

### Stack completa via docker-compose (API + Prometheus + Grafana)

`docker-compose.yml` orquestra os três serviços como **containers separados** (não junta tudo numa
imagem só — cada um mantém seu ciclo de vida, escalabilidade e imagem oficial independentes; ver
decisão nº 9 abaixo para o porquê).

| Ação | Comando |
|---|---|
| Subir tudo (build da API + Prometheus + Grafana) | `docker compose up -d --build` |
| Ver status dos containers | `docker compose ps` |
| Ver logs de todos os serviços | `docker compose logs -f` |
| Desligar tudo | `docker compose down` |

Dashboard em `http://localhost:3000/d/personalization-service` (autenticação anônima habilitada
só para essa demo local, ver seção de observabilidade abaixo).

### Endpoints

| Rota | Descrição |
|---|---|
| `GET /health` | health check simples |
| `GET /recommendations/{user_id}?top_n=10` | ranking de produtos para o usuário, com score do modelo |
| `GET /metrics` | métricas Prometheus (contagem de requests, latência, erros) |
| `GET /docs` | documentação interativa (Swagger, gerada pelo FastAPI) |

---

## Decisões de arquitetura e trade-offs

### 1. Features pré-computadas em batch, não calculadas em request-time

`ingestion/build_features.py` roda como job offline (no build da imagem Docker) e gera um parquet
com a matriz completa `user_id × product_id` já com as 5 features do modelo. A API só **lê** esse
parquet no startup (`app/model_service.py`) e nunca recalcula nada por request.

**Por quê:** os dados recebidos são um snapshot histórico, não um stream em tempo real — não fazia
sentido pagar o custo de groupby/join a cada requisição HTTP. Isso também simplifica o teste da
lógica de features, que fica isolada e sem I/O.

**Trade-off aceito:** se o histórico de eventos mudar, é preciso rodar o job de novo (ou rebuildar
a imagem) para atualizar as recomendações — não há atualização em tempo real. Um usuário novo que
começa a interagir com o catálogo continua sendo tratado como cold start até o próximo ciclo de
ingestão rodar; a API não escreve de volta em `events.csv`, só lê o snapshot pronto.

**O que eu faria diferente com mais tempo:** um pipeline de ingestão incremental — reprocessar
periodicamente (ex: a cada hora) ou por streaming de eventos (Kinesis/similar), e separar o
artefato de dados do build da imagem Docker (publicar em S3 versionado, API busca o mais recente
no startup), para não acoplar atualização de dado a deploy de código.

### 2. Derivação de `user_affinity_match`

Calculada juntando `events.csv` + `products.csv` por `product_id`, contando interações por
usuário/categoria, e escolhendo a categoria com maior contagem como "categoria de afinidade" de
cada usuário (`ingestion/features.py`).

**Critério de desempate:** em caso de empate na contagem, escolho a categoria com maior
`popularity_score` médio entre os produtos empatados; se ainda empatar, desempato por ordem
alfabética — garante um resultado determinístico, sem aleatoriedade.

**Simplificação assumida:** `interactions` conta qualquer `event_type` (view/click/add_to_cart/
purchase) igualmente. O model_card não distingue por tipo de evento no cálculo de referência, e
optei por manter a lógica mais simples e mais próxima da definição de referência usada para gerar
os dados de treino, em vez de introduzir uma ponderação que o modelo não foi treinado esperando ver.

**O que eu faria diferente com mais tempo:** ponderar a afinidade por tipo de evento (compra pesa
mais que view) e por recência (usando a coluna `timestamp`, hoje não utilizada) — ambos os sinais
já existem no dado bruto e não são explorados.

### 3. Cold start unificado no mesmo caminho de código

Quando `user_id` não existe no histórico (`app/model_service.py::recommend`), trato o usuário como
neutro (`interactions=0`, `user_affinity_match=0`) para todos os produtos do catálogo e deixo o
próprio modelo pontuar usando só as features de produto (`price`, `avg_rating`,
`popularity_score`). Na prática, o ranking se aproxima de "produtos mais populares/bem avaliados".

**Por quê:** usuário conhecido e cold start convergem na mesma linha de scoring (`_score()`) — só
muda de onde vêm os dados de entrada. Isso evita duplicar a lógica de ranking em dois caminhos de
código que poderiam divergir com o tempo, e mantém a garantia do case de que "o score do modelo
deve ser a base do ranking" mesmo no fallback.

### 4. Validação de input separada de cold start

`app/validation.py` normaliza (trim + lowercase) e valida o formato do `user_id` (`u_` + 4 dígitos,
observado nos dados reais) **antes** de qualquer lógica de negócio. Um `user_id` malformado (typo,
caracteres inválidos, tamanho absurdo, vazio) retorna `400 Bad Request`; um `user_id` bem formado
mas ausente no histórico continua caindo em cold start (`200`).

**Por quê:** misturar os dois casos faria qualquer input inválido virar silenciosamente uma
resposta "válida" genérica, escondendo bugs de integração do lado de quem consome a API. O
`user_id` nunca é interpolado em SQL/shell (só comparação de string e lookup de índice em memória),
então essa validação é sobre qualidade de contrato de API, não sobre um vetor de injeção real.

### 5. FastAPI como framework de API

Escolhido por: validação automática de tipos via type hints (rejeita `top_n` fora do range 1-60
sem código manual); `TestClient` embutido, usado no teste de integração; suporte nativo a
`lifespan` para carregar modelo/dados uma única vez no startup; documentação Swagger automática;
e integração pronta com `prometheus-fastapi-instrumentator` para métricas.

O endpoint principal é `def` síncrono, não `async def` — tudo que ele faz (lookup em memória,
`scaler.transform`, `model.predict_proba`) é I/O-free e síncrono por natureza; o FastAPI já
executa handlers síncronos em threadpool, então múltiplos requests continuam sendo atendidos em
paralelo sem necessidade de `await`. `async def` só compensaria se o handler fizesse alguma
chamada de rede real (ex: um banco via driver assíncrono).

### 6. Classe `RecommendationService` em vez de funções soltas

Encapsula modelo, scaler e features carregados **uma única vez** no `__init__`, reaproveitados em
todo request subsequente sem I/O repetido. Funções soltas não têm memória própria entre chamadas —
alguém teria que ficar reentregando modelo/scaler a cada chamada. O construtor aceita os caminhos
de arquivo como parâmetro com valor padrão, o que facilita troca de dependência em teste (injeção
de dependência) sem alterar a lógica interna.

### 7. Sem mock nos testes

Nos testes de feature engineering não há dependência externa a substituir — é cálculo puro sobre
DataFrames em memória, então uso dado sintético em vez de mock. No teste de integração, o objetivo
é justamente o oposto de isolar: provar que as peças reais (modelo, scaler, parquet, servidor) se
encaixam de verdade — mockar qualquer uma delas destruiria o propósito do teste. Mock teria feito
sentido para simular uma falha específica de uma dependência (ex: modelo lançando exceção), cenário
que não estava no escopo definido pelo case.

### 8. Job de ingestão rodando no build da imagem Docker

`RUN python -m ingestion.build_features` acontece durante o `docker build`, não no startup do
container — o container sobe já com o parquet pronto, startup rápido e sem dependência externa.

**Trade-off aceito:** atualizar os dados exige rebuild + redeploy da imagem, não só reiniciar o
container. Documentado como decisão consciente de simplicidade em troca de atualização em tempo
real (ver item 1).

### 9. Containers separados para API, Prometheus e Grafana (não uma imagem única)

`docker-compose.yml` define três serviços, cada um com sua própria imagem e ciclo de vida — não
embuti Prometheus/Grafana dentro da imagem da API.

**Por quê:** segue o princípio de um processo principal por container. Cada serviço pode ser
atualizado, escalado e substituído de forma independente (ex: trocar a versão do Grafana sem
rebuildar a API); as imagens oficiais `prom/prometheus` e `grafana/grafana` já são mantidas e
atualizadas pelos próprios projetos, evitando reinventar isso dentro do meu próprio build; e uma
falha num serviço (ex: Grafana trava) não arrasta os outros junto, diferente de um único processo
supervisionando tudo dentro do mesmo container.

`docker compose up -d --build` sobe os três de uma vez sem juntar nada; `docker compose down`
desliga todos juntos. Em produção, o equivalente seria um Pod por serviço no Kubernetes, ou
serviços gerenciados separados (ver seção de observabilidade abaixo).

### 10. CI, sem CD

`.github/workflows/ci.yml` roda automaticamente a cada `push`/`pull request` para `main`: instala
dependências, roda o job de ingestão, roda os 28 testes (`pytest`), e builda + sobe a imagem Docker
validando o `/health` — o gate mínimo antes de qualquer merge.

**Por que só CI, sem CD (deploy automático):** CD exige um alvo real para publicar (registry de
imagens, cluster/serviço de nuvem, credenciais) — nada disso existe neste projeto, que não tem
infraestrutura provisionada. Implementar CD sem alvo real seria simular um passo que não faz
sentido sem a AWS por trás (ver discussão de arquitetura AWS/Terraform, que ficou como conceito,
não implementação). CI sozinho já entrega o valor real disponível agora: nenhum código quebrado
chega a `main` sem passar por teste e build.

---

## O que eu faria diferente com mais tempo

- **Ingestão incremental**, para que cold start se resolva sozinho conforme o usuário interage,
  em vez de depender de um novo build/deploy.
- **Ponderar `user_affinity_match` por tipo de evento e recência**, usando dados já disponíveis
  (`event_type`, `timestamp`) que hoje não são explorados.
- **Separar artefato de dados do build da imagem** — publicar o parquet versionado em S3 e ter a
  API buscar a versão mais recente no startup, desacoplando atualização de dado de deploy de código.
- **Autoscaling e infraestrutura como código** (Terraform/CDK) para o deploy em nuvem — hoje
  ficou como discussão de arquitetura, sem provisionamento real.
- **Regra de negócio para produtos já comprados**: hoje o ranking pode recomendar um produto que o
  usuário já comprou; um filtro de exclusão (ou penalização) seria uma melhoria de produto natural.

## O que eu loga/meço hoje e o que adicionaria com mais tempo

**Hoje:**
- Log estruturado em JSON (via `structlog`) em todo request principal, com `user_id`, `latency_ms`
  (medida em torno da chamada ao `RecommendationService`) e `cold_start` — os três campos pedidos
  explicitamente pelo case.
- Log de aviso (`invalid_user_id`) para toda tentativa de request com `user_id` malformado.
- `/metrics` em formato Prometheus (via `prometheus-fastapi-instrumentator`): contagem de requests
  por rota/status code, e um histograma de latência do qual dá para derivar p50/p95.
- Métrica de negócio dedicada `recommendation_requests_total{cold_start=...}` (via
  `prometheus_client.Counter`), permitindo calcular a taxa de cold start como sinal de produto
  (quantos usuários novos recebem recomendação não-personalizada), não só sinal técnico.
- `HEALTHCHECK` no Dockerfile batendo em `/health`, usado por Docker/ECS para saber quando reiniciar
  um container travado.
- **Stack de observabilidade real, conectada, via `docker-compose.yml`**: Prometheus faz scrape do
  `/metrics` da API a cada 5s; Grafana sobe com datasource e um dashboard já provisionados
  (`observability/`), sem configuração manual — requests/s por status, latência p50/p95, taxa de
  erro 5xx e taxa de cold start, todos atualizando ao vivo. `docker compose up -d` sobe os três
  serviços; dashboard em `http://localhost:3000/d/personalization-service` (auth anônima habilitada
  só para essa demo local, não usar esse modo em produção).

**Adicionaria com mais tempo:**
- Alertas configurados sobre thresholds de latência (p95) e taxa de erro (ex: via Alertmanager).
- Tracing distribuído com um trace ID amarrando todos os logs de uma mesma requisição — relevante
  caso este serviço passe a chamar outros serviços no futuro.
- Em produção real, trocar a autenticação anônima do Grafana por login/SSO, e mover
  Prometheus/Grafana para um serviço gerenciado (Amazon Managed Prometheus/Grafana) em vez de
  containers próprios sem persistência.

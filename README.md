# Personalization Service

[![CI](https://github.com/Melissa-Etes/CASE-ITAU-ENGML/actions/workflows/ci.yml/badge.svg)](https://github.com/Melissa-Etes/CASE-ITAU-ENGML/actions/workflows/ci.yml)

Microsserviço HTTP que serve recomendações personalizadas de produtos a partir de um modelo de
propensão de compra **já treinado** (sklearn `LogisticRegression`). O foco do case é 100%
engenharia: ingestão de dados, API, tratamento de edge cases, testes e observabilidade — não
treino ou melhoria do modelo.

## Stack

- **Python 3.12+** · **FastAPI** (API) · **pandas / pyarrow** (features) · **scikit-learn** (modelo)
- **structlog** (logs JSON) · **prometheus-fastapi-instrumentator** (métricas)
- **pytest** (testes) · **Docker**

## Como rodar

### Local

```bash
pip install -r requirements.txt
python -m ingestion.build_features   # gera data/processed/user_product_features.parquet
uvicorn app.main:app --reload
```

API em `http://localhost:8000` · documentação interativa em `http://localhost:8000/docs`.

### Docker

```bash
docker build -t personalization-service .
docker run -d --name pers -p 8000:8000 personalization-service
curl http://localhost:8000/health
```

O job de ingestão roda **dentro do build da imagem** — o container já sobe com as features
pré-computadas, sem depender de nada externo no startup.

### Stack de observabilidade (Prometheus + Grafana)

```bash
docker compose up -d --build
```

Sobe a API + Prometheus (faz scrape de `/metrics` a cada 5s) + Grafana, com datasource e dashboard
já provisionados automaticamente. Dashboard em `http://localhost:3000/d/personalization-service`
(sem necessidade de login — autenticação anônima habilitada só para essa demo local).

```bash
docker compose down
```

### Testes

```bash
pytest -v
```

26 testes: unitários de feature engineering, unitários de validação de input, testes do endpoint
principal (usuário conhecido, cold start, validação de parâmetros) e um teste de integração real
via `TestClient` — sobe a aplicação inteira, sem mockar nenhuma camada interna.

## Endpoints

| Rota | Descrição |
|---|---|
| `GET /health` | health check |
| `GET /recommendations/{user_id}?top_n=10` | ranking de produtos para o usuário, com score do modelo |
| `GET /metrics` | métricas em formato Prometheus |
| `GET /docs` | documentação interativa (Swagger) |

**Exemplo:**
```bash
curl "http://localhost:8000/recommendations/u_0231?top_n=5"
```
```json
{
  "user_id": "u_0231",
  "cold_start": false,
  "recommendations": [
    {"product_id": "p_032", "score": 0.2065, "category": "esporte", "price": 24.31}
  ]
}
```

## Estrutura do projeto

```
personalization-service/
├── app/
│   ├── main.py            # rotas FastAPI, logging por request
│   ├── model_service.py   # carrega modelo/scaler/features, faz o ranking (inclui cold start)
│   ├── validation.py      # normalização e validação do user_id
│   └── logging_config.py  # logs estruturados em JSON
├── ingestion/
│   ├── features.py        # lógica pura de feature engineering (testável sem I/O)
│   └── build_features.py  # job offline: CSVs -> parquet de features
├── tests/                 # unitários + integração
├── data/                  # events.csv, products.csv (recebidos no case)
├── model/                 # model.pkl, model_card.json (recebidos no case)
├── Dockerfile
└── SOLUTION.md            # decisões de arquitetura, trade-offs e o que faria diferente
```

## Decisões de arquitetura

Resumo rápido — detalhes completos, com o porquê de cada escolha, em [SOLUTION.md](SOLUTION.md):

- **Features pré-computadas em batch**, não em tempo real: dado é um snapshot histórico, API só lê.
- **Cold start** (usuário sem histórico) tratado no mesmo caminho de código do usuário conhecido —
  o modelo pontua usando só as features de produto, sem duplicar lógica de ranking.
- **Validação de input separada de cold start**: `user_id` malformado retorna `400`; `user_id`
  válido mas desconhecido retorna `200` com cold start — evita esconder bugs de integração.
- **Sem mock nos testes**: o teste de integração sobe a aplicação real de propósito, para validar
  que as peças (modelo, scaler, dados) realmente se encaixam.

## O que faria diferente com mais tempo

Ingestão incremental (cold start se resolve sozinho), ponderação de afinidade por tipo de evento e
recência, artefato de dados desacoplado do build da imagem, integração real com stack de
observabilidade e alertas, tracing distribuído. Detalhado em [SOLUTION.md](SOLUTION.md).

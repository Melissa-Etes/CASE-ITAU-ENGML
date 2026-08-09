# SOLUTION_ATUAL.md

Guia prático do estado atual do projeto: como subir tudo no dia a dia, quais URLs usar, como pedir
uma recomendação, e o que cada suíte de teste cobre.

> Para as decisões de arquitetura e trade-offs da entrega original do case, ver [SOLUTION.md](SOLUTION.md).
> Este arquivo documenta uma mudança feita depois: `app/model_service.py` foi substituído por
> `app/service_completo.py` como Model da aplicação (ver seção "O que mudou" abaixo).

---

## Comandos do dia a dia

### Subir tudo (API + Prometheus + Grafana)

```bash
cd CASE-ITAU-ENGML
docker compose up -d --build
```

O `--build` garante que qualquer mudança no código Python entra na imagem antes de subir — sem
ele, o Docker reusa a imagem antiga em cache.

### Ver se está tudo de pé

```bash
docker compose ps
```

Os 3 containers devem aparecer com status `Up` (a API com `(healthy)` depois de alguns segundos).

### Ver logs

```bash
docker compose logs -f          # todos os serviços, seguindo em tempo real
docker compose logs -f api      # só a API
```

### Reconstruir depois de mudar código

Sempre que você editar algo em `app/`, `data/`, ou `model/`, precisa reconstruir a imagem da API
(o código é copiado pra dentro da imagem no build, não fica montado como volume):

```bash
docker compose up -d --build api
```

### Desligar tudo

```bash
docker compose down
```

Remove os containers e a rede, mas mantém os dados de configuração do Grafana/Prometheus que estão
no `observability/` (esses são montados como volume read-only, não se perdem).

### Rodar sem Docker (direto no Python local)

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m ingestion.build_features   # gera data/processed/user_product_features.parquet
uvicorn app.main:app --reload
```

---

## URLs

| O que é | URL | Observação |
|---|---|---|
| API — health check | http://localhost:8000/health | status, versão do modelo, nº de usuários conhecidos, idade dos dados |
| API — documentação interativa (Swagger) | http://localhost:8000/docs | testa os endpoints direto no navegador, sem precisar de `curl` |
| API — métricas Prometheus (cru) | http://localhost:8000/metrics | formato texto do Prometheus, difícil de ler direto — use o Grafana |
| Prometheus — UI | http://localhost:9090 | consultas PromQL manuais; "Status → Targets" mostra se está fazendo scrape da API |
| Grafana — dashboard | http://localhost:3000/d/personalization-service | painéis prontos: requests/s, latência p50/p95, taxa de erro, cold start, distribuição de score, idade dos dados |

Grafana está com autenticação anônima habilitada (só pra essa demo local) — abre direto, sem login.

---

## Como pedir uma recomendação para um usuário

### Usuário conhecido (tem histórico)

```bash
curl http://localhost:8000/recommendations/u_0100
```
```json
{"user_id":"u_0100","cold_start":false,"model_version":"1.0.0","recommendations":[...]}
```

### Usuário desconhecido (cold start — cai no fallback por popularidade/qualidade)

```bash
curl http://localhost:8000/recommendations/u_9999
```
```json
{"user_id":"u_9999","cold_start":true,"model_version":"1.0.0","recommendations":[...]}
```

### Controlando quantas recomendações vêm (`top_n`, entre 1 e 60)

```bash
curl "http://localhost:8000/recommendations/u_0100?top_n=3"
```

### `user_id` com formato inválido (rejeitado antes de chegar no modelo)

```bash
curl -i http://localhost:8000/recommendations/aksjdhakjdsa
```
```
HTTP/1.1 400 Bad Request
{"status_code":400,"detail":"user_id deve seguir o formato 'u_' + 4 digitos (ex: u_0231)"}
```

O formato esperado é `u_` + 4 dígitos (ex: `u_0231`). Maiúsculas são normalizadas automaticamente
(`U_0231` vira `u_0231` e funciona normalmente).

---

## O que mudou: `model_service.py` → `service_completo.py`

O `RecommendationService` original (`app/model_service.py`) foi **removido** e substituído por uma
reimplementação própria, `Recomendador` (`app/service_completo.py`), construída como exercício de
aprendizado, peça por peça:

- `app/recomendador/user_check.py` — `is_known_user(known_users, user_id)`: função pura, decide se
  o usuário já tem histórico.
- `app/recomendador/recommend.py` — `montar_candidatos(...)`: monta a tabela de produtos candidatos
  (histórico real para usuário conhecido, catálogo inteiro com valores neutros para cold start); e
  `ordenar_candidatos_por_score(...)`: pontua e corta para o top N.
- `app/recomendador/score.py` — `scores(...)`: roda o modelo (`scaler.transform` +
  `model.predict_proba`) sobre as features selecionadas.
- `app/service_completo.py` — classe `Recomendador`: carrega modelo/scaler/features/produtos uma
  única vez no `__init__`, e delega a lógica de negócio para as funções acima.

O `Recomendador` mantém **interface idêntica** à do `RecommendationService` original — mesmo
`recommend()` devolvendo `(list[Recommendation], cold_start: bool)`, mesmos atributos
(`model_version`, `known_users`, `features_generated_at`), mesmo fail-fast de integridade do
artefato (`ModelIntegrityError` se o scaler não bater com `feature_cols`). Por isso, trocar a
implementação em `app/dependencies.py` e `app/main.py` não exigiu nenhuma mudança em
`app/routers/recommendations.py`, `app/schemas.py`, no Prometheus, nem no dashboard do Grafana —
todas essas camadas dependem só do **contrato**, não de como o cálculo é feito por dentro.

`app/model_service.py`, `app/model_service_treino.py` (rascunho de exploração inicial) e seus
testes correspondentes foram removidos do projeto por ficarem fora do caminho de execução real.

---

## Testes

Uma suíte só, em `tests/` (a antiga separação em `tests/` + `tests_v2/`, usada
enquanto `model_service.py` e `service_completo.py` coexistiam, foi fundida depois
que `model_service.py` foi removido — não há mais dois "Models" concorrentes para
justificar duas pastas):

```bash
python -m pytest -v
```

| Arquivo | O que testa |
|---|---|
| `test_api.py` (11 testes) | Integração real via `TestClient` do FastAPI: sobe a aplicação inteira (modelo, scaler, dados reais, sem mock) e bate nos endpoints — usuário conhecido ranqueado por score, cold start, `top_n` respeitado e validado (rejeita fora de 1–60), normalização de maiúscula, rejeição de `user_id` malformado com 400 (incluindo tentativas de SQL injection e XSS), corpo de erro padronizado, e métricas (`recommendation_score`, `features_data_age_seconds`) expostas em `/metrics`. |
| `test_features.py` (5 testes) | Unitário, sobre `ingestion/features.py`, com dado sintético em memória (sem I/O) — testa a **lógica** de cálculo: contagem de interações por qualquer tipo de evento, escolha da categoria de maior afinidade do usuário, critério de desempate por popularidade, formato/colunas da matriz de features gerada, e que `user_affinity_match=1` funciona mesmo sem interação direta na categoria. |
| `test_data_quality.py` (11 testes) | Valida o **dado real** (`data/events.csv`, `data/products.csv`), não a lógica — diferente de `test_features.py`. Cobre: colunas esperadas, ausência de nulos, `event_type`/`category` dentro do conjunto conhecido, `product_id` referenciado em `events.csv` existe no catálogo, `price`>0, `avg_rating` 0–5, `popularity_score` 0–1. |
| `test_validation.py` (4 testes, 9 casos parametrizados) | Unitário, sobre `app/validation.py`: normalização de maiúscula/espaço em branco, aceitação de formato válido, e uma bateria de rejeições (vazio, letras no lugar de dígitos, dígitos a mais/a menos, prefixo errado, injeção de SQL, XSS, tamanho absurdo). |
| `test_user_check.py` (4 testes) | `is_known_user` isolada, com sets pequenos "de mentira" — não carrega modelo nem dado real. Cobre: usuário presente, ausente, set vazio, e documenta que a função **não** normaliza maiúscula/minúscula sozinha (é responsabilidade de quem chama). |
| `test_recommend.py` (4 testes) | `montar_candidatos` e `ordenar_candidatos_por_score`, com tabelas pequenas "de mentira". Cobre: cold start devolve o catálogo inteiro com `interactions`/`user_affinity_match` zerados; usuário conhecido devolve só o histórico real dele; ordenação por score decrescente com corte em `top_n`; `top_n` maior que a quantidade de candidatos não quebra. Usa `monkeypatch` do pytest para substituir a função de score por uma falsa (necessário porque `ordenar_candidatos_por_score` importa `scores` diretamente, em vez de recebê-la como parâmetro — uma decisão de design que ficou registrada como ponto de atenção). |
| `test_score.py` (3 testes) | `scores` isolada, com `scaler`/`model` falsos (fakes) previsíveis. Cobre: o índice do resultado bate com o índice do input (importante para o alinhamento posterior no DataFrame); o valor pontuado vem da coluna certa do `predict_proba` (classe 1, não classe 0); colunas extras no input (que não estão em `feature_cols`) são ignoradas sem quebrar. |
| `test_service_completo.py` (14 testes) | `Recomendador` completo, com modelo e dados **reais** (fixture com `scope="module"`, carrega uma única vez). Cobre: `is_known_user` (True/False); `recommend()` devolve o número certo de recomendações e o `cold_start` correto (True/False) para cada caso; cada `Recommendation` tem os 4 campos certos, nos tipos certos; scores vêm ordenados decrescente; **integridade do modelo** — `model_version` e `feature_cols` batem exatamente com `model_card.json`, e o `scaler` foi ajustado para a mesma quantidade de features que `feature_cols` declara; **integridade dos dados** — todo `user_id` carregado do parquet segue o formato `u_XXXX` e está em minúsculo; e que um `user_id` tipo lixo (`"ksajdhakjsd"`) não quebra o `Recomendador` (só cai em cold start). |
| `test_model_quality_gate.py` (3 testes) | Gate de qualidade: compara a distribuição de score do modelo carregado (real) contra um baseline calibrado (`scripts/compute_score_baseline.py`) — falha se o score médio sair da faixa esperada (usuário conhecido ou cold start), ou se os scores colapsarem num valor único (sinal de saturação). |

**Total: 59 funções de teste, 67 casos executados** (a diferença vem dos testes parametrizados em
`test_validation.py`, que rodam 9 vezes com inputs diferentes).

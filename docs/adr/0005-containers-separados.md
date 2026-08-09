# 0005 — Containers separados para API, Prometheus e Grafana

Status: Aceita

## Contexto

A stack de observabilidade (Prometheus + Grafana) precisa rodar junto com a API para a demo
funcionar de ponta a ponta via `docker-compose.yml`. Era possível embutir os três num único
container/imagem, ou mantê-los como três serviços independentes.

## Decisão

`docker-compose.yml` define três serviços com imagens e ciclos de vida próprios —
`personalization-service` (build local), `prom/prometheus` e `grafana/grafana` (imagens oficiais
da comunidade, não reconstruídas).

## Consequências

- Segue o princípio de um processo principal por container — cada serviço pode ser
  atualizado/escalado/substituído independentemente (ex: trocar a versão do Grafana sem
  rebuildar a API).
- Reaproveita imagens oficiais já mantidas e atualizadas pelos próprios projetos Prometheus/
  Grafana, em vez de reinventar isso dentro do build próprio.
- Falha num serviço (ex: Grafana trava) não arrasta os outros junto — diferente de um processo
  supervisor único dentro do mesmo container.
- Trade-off: mais peças móveis para orquestrar localmente (`docker compose up -d --build` sobe
  os três; em produção, o equivalente seria um Pod por serviço no Kubernetes ou serviços
  gerenciados separados).

# Architecture Decision Records

Registro formal das decisões de arquitetura do projeto, no formato padrão ADR
(Contexto → Decisão → Consequências). Complementa o [`SOLUTION.md`](../../SOLUTION.md), que
já cobre as mesmas decisões em tom narrativo — aqui elas ficam em formato curto e consultável,
uma por arquivo, cada uma referenciável por número.

| # | Título | Status |
|---|---|---|
| [0001](0001-features-batch-precomputadas.md) | Features pré-computadas em batch, não em tempo real | Aceita |
| [0002](0002-cold-start-caminho-unico.md) | Cold start no mesmo caminho de scoring do usuário conhecido | Aceita |
| [0003](0003-validacao-separada-de-cold-start.md) | Validação de `user_id` separada da lógica de cold start | Aceita |
| [0004](0004-fastapi-sync-endpoint.md) | FastAPI com endpoint síncrono (`def`, não `async def`) | Aceita |
| [0005](0005-containers-separados.md) | Containers separados para API, Prometheus e Grafana | Aceita |
| [0006](0006-sem-mock-testes-integracao.md) | Sem mock no teste de integração | Aceita |
| [0007](0007-ci-sem-cd.md) | CI automatizado, sem CD | Aceita |
| [0008](0008-recomendador-substitui-model-service.md) | `Recomendador` substitui `model_service.py` como Model | Aceita |

## Template para um ADR novo

```markdown
# NNNN — Título curto, no imperativo

Status: Proposta | Aceita | Substituída por NNNN

## Contexto

Qual problema/força levou a essa decisão precisar ser tomada.

## Decisão

O que foi decidido, de forma direta.

## Consequências

O que fica mais fácil, o que fica mais difícil, e qual trade-off foi aceito conscientemente.
```

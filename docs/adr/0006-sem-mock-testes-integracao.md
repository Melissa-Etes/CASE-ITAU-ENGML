# 0006 — Sem mock no teste de integração

Status: Aceita

## Contexto

`tests/test_api.py` valida o comportamento real da API via `TestClient` do FastAPI. Era possível
mockar o `Recomendador` (ou partes dele — modelo, scaler, parquet) para isolar o teste de
dependências externas, como é comum em testes unitários.

## Decisão

O teste de integração sobe a aplicação **inteira** — modelo real, scaler real, dado real — sem
mockar nenhuma camada interna. O objetivo desse teste específico é justamente o oposto de
isolar: provar que as peças reais se encaixam de verdade.

Os testes unitários (`tests/test_features.py`, `tests/test_user_check.py`,
`tests/test_recommend.py`, `tests/test_score.py`) continuam usando dado sintético/fakes onde faz
sentido isolar lógica — a decisão de não mockar vale especificamente para o teste de integração e
para `tests/test_service_completo.py`/`tests/test_model_quality_gate.py`, que também usam
modelo/dados reais de propósito.

## Consequências

- Pega problemas de "encaixe" entre peças (ex: `feature_cols` do modelo desalinhado com o que o
  código monta) que testes unitários com mock nunca detectariam.
- Mais lento que um teste 100% mockado (carrega parquet + pickle), mas ainda rápido o suficiente
  para rodar em todo push (suíte inteira roda em segundos).
- Mock teria feito sentido para simular uma falha específica de dependência (ex: modelo lançando
  exceção) — cenário fora do escopo definido pelo case, não implementado.

# 0002 — Cold start no mesmo caminho de scoring do usuário conhecido

Status: Aceita

## Contexto

Um `user_id` sem histórico em `events.csv` não tem `interactions` nem `user_affinity_match`
calculáveis. É preciso decidir como ranquear produtos mesmo assim, sem duplicar a lógica de
ranking num caminho de código separado.

## Decisão

`app/recomendador/recommend.py::montar_candidatos` trata o usuário desconhecido como neutro
(`interactions=0`, `user_affinity_match=0`) para todo o catálogo, e devolve essa tabela para o
**mesmo** `ordenar_candidatos_por_score` / `scores()` que processa usuário conhecido — só muda de
onde vêm os dados de entrada, não a lógica de pontuação em si. Na prática, o ranking de cold
start se aproxima de "produtos mais populares/bem avaliados", porque só as features de produto
(`price`, `avg_rating`, `popularity_score`) diferenciam as linhas.

## Consequências

- Sem duplicação de lógica de ranking entre os dois caminhos — um único `scores()` para manter.
- O score do modelo continua sendo a base do ranking mesmo no fallback (não é um "modo especial"
  desconectado do modelo).
- Trade-off: o cold start é sempre "genérico por popularidade" — não há personalização nenhuma
  até o usuário aparecer num próximo ciclo de ingestão (ver ADR 0001).
- `tests/test_recommend.py::test_cold_start_devolve_catalogo_inteiro_com_zeros` e
  `tests/test_service_completo.py::test_recommend_cold_start_todos_tem_interactions_zero` travam
  essa decisão.

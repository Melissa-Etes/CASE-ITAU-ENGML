# 0007 — CI automatizado, sem CD

Status: Aceita

## Contexto

`.github/workflows/ci.yml` roda a cada push/PR para `main`. Um pipeline de CI/CD completo
incluiria deploy automático (CD) além de teste e build — mas CD exige um alvo real para publicar
(registry de imagens, cluster/serviço de nuvem, credenciais), nenhum dos quais existe
provisionado para este projeto.

## Decisão

O CI cobre: instalar dependências, rodar o job de ingestão, rodar a suíte de testes completa
(`pytest -v` — inclui os gates de qualidade de dado e modelo), buildar a imagem Docker com tag
versionada por commit (`personalization-service:${{ github.sha }}`), validar o `/health`, e
escanear vulnerabilidades (Trivy). Não há step de deploy.

## Consequências

- Garante que nenhum código quebrado (ou modelo/dado fora do baseline de qualidade) chega em
  `main` sem passar por teste e build — o gate mínimo real e útil disponível hoje.
- Imagem versionada por commit permite rastrear exatamente qual código gerou qual build (ver ADR
  relacionado em `docs/ROUTING.md` → "Mudar como o CI builda/testa").
- Implementar CD sem alvo real seria simular um passo que não faz sentido sem infraestrutura de
  nuvem provisionada por trás — discussão de arquitetura (AWS/Terraform) ficou como conceito, não
  implementação, dentro do escopo e prazo do case.

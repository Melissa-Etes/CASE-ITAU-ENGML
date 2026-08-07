# Digest fixado (nao so a tag "3.12-slim", que e movel e muda de conteudo com
# o tempo) -- builds reproduziveis: o mesmo Dockerfile gera a mesma imagem
# base hoje e daqui a 6 meses. Atualizar o digest e uma decisao explicita
# (bump manual ou automatizado via Dependabot), nao um efeito colateral de
# alguem rebuildar.
ARG PYTHON_IMAGE=python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b

# ---- stage 1: builder -------------------------------------------------
# So essa stage instala dependencias (e o cache de pip que isso gera). Nada
# daqui sobra na imagem final -- so o resultado (o venv) e copiado adiante.
FROM ${PYTHON_IMAGE} AS builder

WORKDIR /srv

COPY requirements.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- stage 2: runtime ---------------------------------------------------
# Imagem final: so o venv pronto (sem pytest/httpx -- ficam em
# requirements-dev.txt, usados apenas no CI) + o codigo + os dados/modelo.
FROM ${PYTHON_IMAGE}

WORKDIR /srv

COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

# Copia o codigo e os dados/modelo recebidos no case
COPY app/ app/
COPY ingestion/ ingestion/
COPY data/events.csv data/products.csv data/
COPY model/ model/

# Gera o parquet de features no build da imagem (job offline, ver SOLUTION.md
# para o trade-off dessa escolha vs. rodar como job separado/agendado).
RUN python -m ingestion.build_features

# Usuario nao-root -- boa pratica de seguranca em producao
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

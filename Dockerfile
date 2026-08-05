FROM python:3.12-slim

WORKDIR /srv

# Instala dependencias primeiro (camada cacheada -- so reinstala se requirements.txt mudar)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

"""Job de ingestao: le data/events.csv + data/products.csv e escreve o parquet
de features pre-computadas usado pela API no startup.

Roda offline (build da imagem Docker ou job agendado), nao faz parte do runtime
da API. Ver SOLUTION.md para o trade-off dessa escolha.

Uso:
    python -m ingestion.build_features
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ingestion.features import build_feature_matrix

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "processed" / "user_product_features.parquet"


def main() -> None:
    events_path = DATA_DIR / "events.csv"
    products_path = DATA_DIR / "products.csv"

    logger.info("lendo %s e %s", events_path, products_path)
    events = pd.read_csv(events_path)
    products = pd.read_csv(products_path)

    logger.info("events=%d linhas, products=%d linhas", len(events), len(products))

    matrix = build_feature_matrix(events, products)
    logger.info("matriz de features gerada: %d linhas (%d usuarios x %d produtos)",
                len(matrix), events["user_id"].nunique(), products["product_id"].nunique())

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    matrix.to_parquet(OUTPUT_PATH, index=False)
    logger.info("features salvas em %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()

"""Funcao pura: calcula o score do modelo para cada linha candidata.
"""

import pandas as pd


def scores(
    produtos_candidatos,
    feature_cols,
    scaler,
    model,
) -> pd.Series:

    # Seleciona apenas as colunas de features relevantes para o modelo,
    # na ordem que o scaler/model esperam
    X = produtos_candidatos[feature_cols]
    # Normaliza (mesma escala usada no treino)
    X_scaled = scaler.transform(X)

    # predict_proba devolve [prob classe 0, prob classe 1] por linha --
    # [:, 1] pega so a probabilidade da classe positiva (vai comprar)
    scores = model.predict_proba(X_scaled)[:, 1]

    # Embrulha em Series com o mesmo indice do input, para o pandas
    # alinhar cada score com a linha certa quando isso virar uma coluna nova
    return pd.Series(scores, index=produtos_candidatos.index)



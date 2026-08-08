"""Funcao pura: calcula o score do modelo para cada linha candidata.
"""

import pandas as pd


def scores(
    produtos_candidatos,
    feature_cols,
    scaler,
    model,
) -> pd.Series:

    # Seleciona apenas as colunas de features relevantes para o modelo
    X = produtos_candidatos[feature_cols]
    X_scaled = scaler.transform(X)
    
    scores = model.predict_proba(X_scaled)[:, 1]  

    return pd.Series(scores, index=produtos_candidatos.index)



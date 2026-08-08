

# IMPORTS
import pickle
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model" / "model.pkl"

MODELO = pickle.load(open(MODEL_PATH, "rb"))


class Recomendador:
    def __init__(self, MODELO):
        self.model = MODELO["model"]
        self.scaler = MODELO["scaler"]
        self.feature_cols = MODELO["feature_cols"]

        self.features = pd.read_parquet(BASE_DIR / "data" / "processed" / "user_product_features.parquet").set_index("user_id")
        self.products = pd.read_csv(BASE_DIR / "data" / "products.csv").set_index("product_id")
        self.known_users = set(self.features.index.unique())

r = Recomendador(MODELO)



# ==== TESTE ====
# print(r.known_users)
# print(len(r.known_users))


# user_id = "u_0100"  
# linha = r.features.loc[[user_id]]
# print(linha)


# print(dir(r.scaler))

dados = r.features 
X = dados[r.feature_cols]
X_scaled = r.scaler.transform(X)

tabela = pd.DataFrame(X_scaled)
print(pd.DataFrame(X_scaled).head())
print(tabela.head())
print(tabela.shape)
print(r.model.classes_)
print(type(r.model))
print("pesos:", r.model.coef_)


scores = r.model.predict_proba(X_scaled)[:, 1]


# Reexporta as funcoes puras do pacote, para poder importar direto de
# app.recomendador em vez de precisar saber em qual arquivo cada uma mora.
from .user_check import is_known_user
from .recommend import montar_candidatos, ordenar_candidatos_por_score
from .score import scores
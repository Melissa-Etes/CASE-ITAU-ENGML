"""Testes de app/recomendador/user_check.py

is_known_user() e uma funcao pura: recebe known_users (set) e user_id (str),
devolve True/False. Nao carrega nada, nao depende de arquivo/modelo -- por
isso os testes aqui sao rapidos e usam sets pequenos "de mentira", sem
precisar instanciar o Recomendador nem tocar em disco.
"""

from app.recomendador.user_check import is_known_user


def test_true_quando_user_id_esta_no_set():
    """Caso feliz: o user_id pedido existe dentro do known_users."""
    known = {"u_0001", "u_0002", "u_0003"}

    assert is_known_user(known, "u_0001") is True


def test_false_quando_user_id_nao_esta_no_set():
    """Usuario nao encontrado -> False (e a partir daqui, quem chama decide
    seguir pelo caminho de cold start)."""
    known = {"u_0001", "u_0002", "u_0003"}

    assert is_known_user(known, "u_9999") is False


def test_false_quando_set_esta_vazio():
    """Caso de borda: known_users vazio (ex: parquet de features vazio, ou
    ainda nao carregado). Nenhum user_id pode ser considerado conhecido."""
    known = set()

    assert is_known_user(known, "u_0001") is False


def test_case_sensitive():
    """Documenta um comportamento importante: a funcao NAO normaliza
    maiusculo/minusculo sozinha. "U_0001" (maiusculo) e tratado como um
    valor diferente de "u_0001" (minusculo), porque sets de string em
    Python comparam caractere a caractere, sem normalizar.

    Isso significa que normalizar o user_id (ex: user_id.lower()) e
    responsabilidade de quem CHAMA essa funcao -- nao dela. Esse teste existe
    para deixar essa decisao de design registrada e visivel, nao so
    documentada em comentario.
    """
    known = {"u_0001"}

    assert is_known_user(known, "U_0001") is False

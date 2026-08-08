# Compara um valor com um conjunto de valores conhecidos, para verificar se o usuário é conhecido ou não.
# TRUE OU FALSE APENAS

def is_known_user(known_users: set, user_id: str) -> bool:


# "-> bool" type hint, chegou no python 3.5, é uma forma de documentar o tipo de dado que a função espera receber e retornar.

# set é um quando procura-se por um elemento, é mais rápido que uma lista ou tupla.

    """Verifica se o usuário é conhecido.

    Args:
        known_users (set): Conjunto de IDs de usuários conhecidos.
        user_id (str): ID do usuário a ser verificado.

    Returns:
        bool: True se o usuário for conhecido, False caso contrário.
    """
    return user_id in known_users


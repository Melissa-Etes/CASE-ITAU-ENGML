import pytest

from app.validation import InvalidUserIdError, normalize_user_id


# Maiuscula vira minuscula
def test_normalizes_uppercase_to_lowercase():
    assert normalize_user_id("U_0231") == "u_0231"


# Espaco em branco nas pontas e removido
def test_strips_surrounding_whitespace():
    assert normalize_user_id("  u_0231  ") == "u_0231"


# Formato ja valido passa direto, sem alteracao
def test_accepts_valid_id_unchanged():
    assert normalize_user_id("u_0231") == "u_0231"


@pytest.mark.parametrize(
    "bad_input",
    [
        "",
        "   ",
        "u_abc1",           # letras no lugar dos digitos
        "u_123",            # digitos de menos
        "u_00231",          # digitos demais
        "x_0231",           # prefixo errado
        "u_0231; DROP TABLE users;",
        "<script>alert(1)</script>",
        "u_0231" + "a" * 100,  # tamanho absurdo
    ],
)
# Cada valor da lista acima deve lancar InvalidUserIdError (roda 9x, um por caso)
def test_rejects_invalid_user_ids(bad_input):
    with pytest.raises(InvalidUserIdError):
        normalize_user_id(bad_input)

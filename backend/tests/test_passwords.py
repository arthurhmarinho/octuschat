"""Hash de senha (scrypt): ida e volta, adulteração e formato inválido."""

import pytest

from app.core import passwords


def test_ida_e_volta():
    stored = passwords.hash_password("uma-senha-longa-ok")
    assert stored.startswith("scrypt$")
    assert passwords.verify_password("uma-senha-longa-ok", stored)


def test_senha_errada():
    stored = passwords.hash_password("uma-senha-longa-ok")
    assert not passwords.verify_password("outra-senha-longa", stored)


def test_mesma_senha_gera_hashes_diferentes():
    a = passwords.hash_password("uma-senha-longa-ok")
    b = passwords.hash_password("uma-senha-longa-ok")
    assert a != b  # salt aleatório


def test_hash_adulterado():
    stored = passwords.hash_password("uma-senha-longa-ok")
    head, last = stored.rsplit("$", 1)
    flipped = ("A" if last[0] != "A" else "B") + last[1:]
    assert not passwords.verify_password("uma-senha-longa-ok", f"{head}${flipped}")


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "abc",
        "scrypt$16384$8$1$so-quatro",
        "bcrypt$16384$8$1$AAAA$AAAA",
        "scrypt$x$8$1$AAAA$AAAA",
        "scrypt$16384$8$1$@@@$@@@",
        "scrypt$16384$8$1$AAAA$",
    ],
)
def test_formato_invalido_da_false_sem_levantar(stored):
    assert passwords.verify_password("qualquer", stored) is False


def test_parametros_absurdos_nao_derrubam():
    # N não potência de 2 / zero: o scrypt recusa; o verify devolve False.
    assert not passwords.verify_password("x", "scrypt$3$8$1$AAAA$AAAA")
    assert not passwords.verify_password("x", "scrypt$0$0$0$AAAA$AAAA")


def test_politica_de_tamanho_minimo():
    with pytest.raises(passwords.WeakPassword):
        passwords.check_policy("curta123")  # 8
    passwords.check_policy("1234567890")  # 10 ok

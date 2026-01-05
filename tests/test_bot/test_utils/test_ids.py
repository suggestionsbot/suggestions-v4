import string

from bot.utils import generate_id


def test_default_id_generation():
    r_1: str = generate_id()
    assert len(r_1) == 11
    assert "-" in r_1

    r_2: str = generate_id()
    assert r_2 != r_1, "If this fails, the bot is broken full stop."


def test_id_with_kwargs():
    r_1: str = generate_id(include_sep=False)
    assert len(r_1) == 10
    assert "-" not in r_1

    r_2: str = generate_id(alphabet=string.digits, include_sep=False)
    assert r_2.isnumeric()

    r_3: str = generate_id(unique_length=2, include_sep=False)
    assert len(r_3) == 2

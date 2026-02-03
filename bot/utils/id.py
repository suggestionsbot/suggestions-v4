import string

from fastnanoid import generate

ALPHABET = string.ascii_lowercase + string.digits


def generate_id(
    unique_length: int = 10,
    *,
    include_sep: bool = True,
    alphabet: str = ALPHABET,
) -> str:
    """Returns a unique ID."""
    if include_sep:
        return (
            generate(alphabet, unique_length // 2)
            + "-"
            + generate(alphabet, unique_length // 2)
        )

    return generate(alphabet, unique_length)

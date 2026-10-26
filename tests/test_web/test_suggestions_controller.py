import pytest

from web.controllers.suggestions_controller import person


@pytest.mark.parametrize(
    "display_text,expected",
    [
        ("Vixen (<@123>)", {"name": "Vixen", "mention": "Vixen", "user_id": 123}),
        ("Vixen (<@!123>)", {"name": "Vixen", "mention": "Vixen", "user_id": 123}),
        # Rows migrated from v3 only store the mention
        ("<@123>", {"name": None, "mention": "123", "user_id": 123}),
        # generate_author_text() with no user_name
        ("None (<@123>)", {"name": None, "mention": "123", "user_id": 123}),
        ("Anonymous", {"name": "Anonymous", "mention": None, "user_id": None}),
        (None, {"name": "Unknown", "mention": None, "user_id": None}),
    ],
)
def test_person(display_text, expected):
    assert person(display_text) == expected

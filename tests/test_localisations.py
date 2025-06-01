import lightbulb
import pytest

from bot.exceptions import MissingTranslation
from bot.localisation import Localisation


def test_expected_lookup(localisation: Localisation, context: lightbulb.Context):
    assert (
        localisation.get_localized_string("commands.suggest.name", context) == "suggest"
    )


def test_unexpected_lookup(localisation: Localisation, context: lightbulb.Context):
    with pytest.raises(MissingTranslation):
        localisation.get_localized_string("commands.doesnt_exist.name", context)


def test_falls_back(localisation: Localisation, context: lightbulb.Context):
    # N.b this test will fail if all locales actually have consistent translations
    context.interaction.locale = "fr"
    assert (
        localisation.get_localized_string(
            "errors.suggest.content_too_long.title",
            context,
        )
        == "Command Failed"
    )


# noinspection PyPropertyAccess
def test_templating(localisation: Localisation, context: lightbulb.Context):
    assert (
        localisation.inject_locale_values(
            "$TEST",
            extras={"TEST": "test"},
            ctx=context,
        )
        == "test"
    )

    context.channel_id = 1
    context.user.id = 2
    context.guild_id = 3
    assert (
        localisation.inject_locale_values(
            "$CHANNEL_ID $AUTHOR_ID $GUILD_ID",
            ctx=context,
        )
        == "1 2 3"
    )

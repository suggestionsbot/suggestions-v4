import lightbulb
import pytest

from bot.exceptions import MissingTranslation
from bot.localisation import Localisation


def test_expected_lookup(localisation: Localisation, ctx: lightbulb.Context):
    assert localisation.get_localized_string("commands.suggest.name", ctx) == "suggest"


def test_unexpected_lookup(localisation: Localisation, ctx: lightbulb.Context):
    with pytest.raises(MissingTranslation):
        localisation.get_localized_string("commands.doesnt_exist.name", ctx)


def test_falls_back(localisation: Localisation, ctx: lightbulb.Context):
    # N.b this test will fail if all locales actually have consistent translations
    ctx.interaction.locale = "fr"
    assert (
        localisation.get_localized_string(
            "values.suggest.content_too_long_title",
            ctx,
        )
        == "Command Failed"
    )


# noinspection PyPropertyAccess
def test_templating(localisation: Localisation, ctx: lightbulb.Context):
    assert (
        localisation.inject_locale_values(
            "$TEST",
            extras={"TEST": "test"},
            ctx=ctx,
        )
        == "test"
    )

    ctx.channel_id = 1
    ctx.user.id = 2
    ctx.guild_id = 3
    assert (
        localisation.inject_locale_values(
            "$CHANNEL_ID $AUTHOR_ID $GUILD_ID",
            ctx=ctx,
        )
        == "1 2 3"
    )

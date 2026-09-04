import lightbulb
import pytest

from bot.exceptions import MissingTranslation
from bot.localisation import Localisation


def test_expected_lookup(localisation: Localisation, context: lightbulb.Context):
    assert (
        localisation.get_localized_string(
            "commands.suggest.name", context.interaction.locale
        )
        == "suggest"
    )


def test_unexpected_lookup(localisation: Localisation, context: lightbulb.Context):
    with pytest.raises(MissingTranslation):
        localisation.get_localized_string(
            "commands.doesnt_exist.name", context.interaction.locale
        )


def test_falls_back(localisation: Localisation, context: lightbulb.Context):
    # N.b this test will fail if all locales actually have consistent translations
    context.interaction.locale = "fr"
    assert (
        localisation.get_localized_string(
            "errors.suggest.content_too_long.title",
            context.interaction.locale,
        )
        == "Command Failed"
    )

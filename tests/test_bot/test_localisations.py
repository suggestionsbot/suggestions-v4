import hikari
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


def test_falls_back(
    localisation: Localisation,
    context: lightbulb.Context,
    monkeypatch: pytest.MonkeyPatch,
):
    context.interaction.locale = "fr"
    monkeypatch.delitem(
        localisation.lightbulb_provider.localizations[hikari.Locale.FR],
        "errors.suggest.content_too_long.title",
    )
    assert (
        localisation.get_localized_string(
            "errors.suggest.content_too_long.title",
            context.interaction.locale,
        )
        == "Command Failed"
    )


def test_every_suggestion_state_is_translated(localisation: Localisation):
    from shared.tables.suggestion import SuggestionStateEnum

    for state in SuggestionStateEnum:
        localisation.get_localized_string(
            f"values.state.{state.value.lower()}", hikari.Locale.EN_GB
        )


def test_strings_fit_discord_limits(localisation: Localisation):
    import re

    command_name = re.compile(r"^[-_\w]{1,32}$")
    choice = re.compile(r"\.(choices\.\d+|filter\.\d+)\.name$")
    for locale, data in localisation.lightbulb_provider.localizations.items():
        for key, value in data.items():
            where = f"{locale} {key}"
            if key.startswith("commands.") and ".responses." not in key:
                if choice.search(key) or key.endswith(".description"):
                    assert len(value) <= 100, where  # noqa: PLR2004
                elif key.endswith(".name"):
                    assert command_name.match(value), where
                    assert value == value.lower(), where
            is_modal_label = key.startswith(
                "menus.guild_configuration.premium_menu.custom_"
            ) and key.endswith(".title")
            if is_modal_label or key.endswith(".modal_title"):
                assert len(value) <= 45, where  # noqa: PLR2004

import disnake

from bot import SuggestionsBot
from bot.tables import GuildConfig


def test_get_localized_string(bot: SuggestionsBot, fake_interaction):
    r_1 = bot.get_localized_string("SUGGEST_NAME", fake_interaction)
    assert r_1 == "suggest"

    fake_interaction.locale = disnake.Locale.da
    r_2 = bot.get_localized_string("SUGGEST_NAME", fake_interaction)
    assert r_2 == "forslå"


def test_inject_locale_values(bot: SuggestionsBot, fake_interaction):
    r_1 = bot.inject_locale_values("$AUTHOR_ID", fake_interaction)
    assert r_1 == f"{fake_interaction.author.id}"

    gc = GuildConfig(id=123)
    r_2 = bot.inject_locale_values(
        "$GUILD_CONFIG_KEEP_LOGS", fake_interaction, guild_config=gc
    )
    assert r_2 == f"{gc.keep_logs}"

    gc.keep_logs = True
    r_3 = bot.inject_locale_values(
        "$GUILD_CONFIG_KEEP_LOGS", fake_interaction, guild_config=gc
    )
    assert r_3 == f"{gc.keep_logs}"

import json
from pathlib import Path
from string import Template

import hikari
import lightbulb
import logoo
from lightbulb import DictLocalizationProvider

from bot.exceptions import MissingTranslation
from bot.tables import GuildConfig

logger = logoo.Logger(__name__)


class Localisation:
    def __init__(self, base_path: Path = Path(".")):
        self._file_to_locale: dict[Path, hikari.Locale] = {
            base_path / Path("locales/da.json"): hikari.Locale.DA,
            base_path / Path("locales/de.json"): hikari.Locale.DE,
            base_path / Path("locales/en_GB.json"): hikari.Locale.EN_GB,
            base_path / Path("locales/en_US.json"): hikari.Locale.EN_US,
            base_path / Path("locales/fr.json"): hikari.Locale.FR,
            base_path / Path("locales/pt_BR.json"): hikari.Locale.PT_BR,
            base_path / Path("locales/tr.json"): hikari.Locale.TR,
        }
        data: dict[hikari.Locale, dict[str, str]] = {}
        for k, v in self._file_to_locale.items():
            with open(k, "r", encoding="utf-8") as f:
                as_dict = json.loads(f.read())
                data[v] = as_dict

        self.lightbulb_provider = DictLocalizationProvider(data)

    def get_locale(self, key: str, locale: hikari.Locale) -> str:
        try:
            return self.lightbulb_provider.localizations[locale][key]
        except KeyError:
            fallback_value = self.lightbulb_provider.localizations[
                hikari.Locale.EN_GB
            ].get(key, None)
            if fallback_value is None:
                logger.critical(f"Could not find base translation for {key}")
                raise MissingTranslation  # TODO Handle this on the bots error handler

            return fallback_value

    @staticmethod
    def inject_locale_values(
        content: str,
        ctx: lightbulb.Context,
        *,
        extras: dict = None,
        guild_config: GuildConfig | None = None,
    ):
        base_config = {
            "CHANNEL_ID": ctx.channel_id,
            "GUILD_ID": ctx.guild_id,
            "AUTHOR_ID": ctx.user.id,
        }
        if extras is not None:
            base_config = {**base_config, **extras}

        if guild_config is not None:
            guild_data = {}
            for k, v in guild_config.to_dict().items():
                guild_data[f"GUILD_CONFIG_{k.upper()}"] = v

            guild_data.pop("GUILD_CONFIG__ID")
            base_config = {**base_config, **guild_data}

        return Template(content).safe_substitute(base_config)

    def get_localized_string(
        self,
        key: str,
        ctx: lightbulb.Context,
        *,
        extras: dict = None,
        guild_config: GuildConfig | None = None,
    ):
        locale = ctx.interaction.locale
        if not isinstance(locale, hikari.Locale):
            locale = hikari.Locale(locale)

        content = self.get_locale(key, locale)
        return self.inject_locale_values(
            content,
            ctx=ctx,
            guild_config=guild_config,
            extras=extras,
        )

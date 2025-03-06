from __future__ import annotations

import logging
from pathlib import Path
from string import Template

import disnake
from disnake import Locale, LocalizationKeyError
from disnake.ext import commands
from logoo import Logger
import redis.asyncio as redis

from bot.tables import GuildConfig
from bot.utils import InteractionHandler

log = logging.getLogger(__name__)
logger = Logger(__name__)


class SuggestionsBot(commands.AutoShardedInteractionBot):
    def __init__(self, *args, redis_instance: redis.Redis, **kwargs):
        super().__init__(*args, **kwargs)
        self.i18n.load(Path("bot/locales"))

        # Set decode_responses to True
        self.redis: redis.Redis = redis_instance

    def get_locale(self, key: str, locale: Locale) -> str:
        values = self.i18n.get(key)
        if not values:
            raise LocalizationKeyError(key)

        try:
            return values[str(locale)]
        except KeyError:
            # Default to known translations if not set
            value = values.get("en-GB")
            if value is None:
                value = values["en-US"]
                logger.critical(
                    "Missing translation in en-GB file",
                    extra_metadata={"translation_key": key},
                )

            return value

    @staticmethod
    def inject_locale_values(
        content: str,
        interaction: disnake.Interaction,
        *,
        extras: dict | None = None,
        guild_config: GuildConfig | None = None,
    ):
        base_config = {
            "CHANNEL_ID": interaction.channel_id,
            "GUILD_ID": interaction.guild_id,
            "AUTHOR_ID": interaction.author.id,
        }
        if extras is not None:
            base_config = {**base_config, **extras}

        if guild_config is not None:
            guild_data = {}
            for k, v in guild_config.to_dict().items():
                guild_data[f"GUILD_CONFIG_{k.upper()}"] = v

            guild_data.pop("GUILD_CONFIG_ID")
            base_config = {**base_config, **guild_data}

        return Template(content).safe_substitute(base_config)

    def get_localized_string(
        self,
        key: str,
        interaction: disnake.Interaction,
        *,
        extras: dict | None = None,
        guild_config: GuildConfig | None = None,
    ):
        content = self.get_locale(key, interaction.locale)
        return self.inject_locale_values(
            content,
            interaction=interaction,
            guild_config=guild_config,
            extras=extras,
        )

from __future__ import annotations

from datetime import timedelta
from typing import cast, TYPE_CHECKING

import commons
import disnake
from commons.caching import NonExistentEntry

from bot.exceptions import ConflictingHandlerInformation

if TYPE_CHECKING:
    from bot import SuggestionsBot


class InteractionHandler:
    """A generic interaction response class to allow for easier
    testing and generification of interaction responses.

    This class also aims to move the custom add-ons out of
    the underlying disnake classes to help promote easier
    version upgrading in the future.
    """

    def __init__(
        self,
        interaction: (
            disnake.Interaction
            | disnake.GuildCommandInteraction
            | disnake.MessageInteraction
        ),
        ephemeral: bool,
        with_message: bool,
    ):
        self.interaction: (
            disnake.Interaction
            | disnake.GuildCommandInteraction
            | disnake.MessageInteraction
        ) = interaction
        self.ephemeral: bool = ephemeral
        self.with_message: bool = with_message
        self.is_deferred: bool = False

        # This is useful in error handling to stop
        # getting discord "Interaction didn't respond"
        # errors if we haven't yet sent anything
        self.has_sent_something: bool = False

    @property
    def bot(self) -> SuggestionsBot:
        return self.interaction.client  # type: ignore

    async def send(
        self,
        content: str | None = None,
        *,
        embed: disnake.Embed | None = None,
        file: disnake.File | None = None,
        components: list | None = None,
        translation_key: str | None = None,
    ):
        if translation_key is not None:
            if content is not None:
                raise ConflictingHandlerInformation

            content = self.bot.get_localized_string(translation_key, self.interaction)

        data = {}
        if content is not None:
            data["content"] = content
        if embed is not None:
            data["embed"] = embed
        if file is not None:
            data["file"] = file
        if components is not None:
            data["components"] = components

        if not data:
            raise ValueError("Expected at-least one value to send.")

        value = await self.interaction.send(ephemeral=self.ephemeral, **data)
        self.has_sent_something = True
        return value

    @classmethod
    async def new_handler(
        cls,
        interaction: disnake.Interaction,
        *,
        ephemeral: bool = True,
        with_message: bool = True,
        defer: bool = True,
    ) -> InteractionHandler:
        """Generate a new instance and defer the interaction."""
        instance = cls(interaction, ephemeral, with_message)

        if defer:
            await interaction.response.defer(
                ephemeral=ephemeral, with_message=with_message
            )
            instance.is_deferred = True

        bot: SuggestionsBot = interaction.client
        await bot.redis.set(
            f"IH:{interaction.id}",
            f"{ephemeral},{with_message},{defer}",
            # Interactions only live for 15 minutes max
            ex=timedelta(minutes=15),
        )

        return instance

    @classmethod
    async def fetch_handler(
        cls,
        interaction: disnake.Interaction,
    ) -> InteractionHandler | None:
        """Fetch a registered handler for the given interaction."""
        result = await interaction.client.redis.get(f"IH:{interaction.id}")
        if not result:
            return None

        ephemeral, with_message, defer = result.split(",")
        instance = cls(
            interaction,
            commons.value_to_bool(ephemeral),
            commons.value_to_bool(with_message),
        )
        instance.is_deferred = commons.value_to_bool(defer)
        return instance

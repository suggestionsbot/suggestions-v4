import io
import logging

import hikari
import lightbulb

from bot import utils
from bot.constants import QUEUE_GROUP, EMBED_COLOR, PAGINATOR_OBJECTS
from bot.hooks import early_ephemeral_defer
from bot.localisation import Localisation
from bot.tables import CommandInvokes, CommandTypes
from bot.utils import QueuedSuggestionsPaginator, generate_id
from shared.tables import (
    GuildConfigs,
    QueuedSuggestions,
    UserConfigs,
)
from shared import utils as shared_utils

logger = logging.getLogger(__name__)


@QUEUE_GROUP.register
class QueueInfoCmd(
    lightbulb.SlashCommand,
    name="commands.queue.info.name",
    description="commands.queue.info.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    hooks=[early_ephemeral_defer],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/queue info",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        queued_suggestions_for_guild: list[QueuedSuggestions] = (
            await QueuedSuggestions.fetch_guild_queued_suggestions(
                guild_id=guild_config.guild_id,
            )
        )
        virtual_count = physical_count = 0
        for qs in queued_suggestions_for_guild:
            if qs.message_id is not None:
                physical_count += 1
            else:
                virtual_count += 1

        desc = io.StringIO()
        desc.write(
            localisations.get_localized_string(
                "commands.queue.info.responses.description_count",
                user_config.primary_language,
                extras={"VIRTUAL": virtual_count, "PHYSICAL": physical_count},
            ),
        )
        desc.write("\n")
        ext = "yes" if guild_config.uses_suggestion_queue else "no"
        desc.write(
            localisations.get_localized_string(
                f"commands.queue.info.responses.description_new_queued.{ext}",
                user_config.primary_language,
            ),
        )

        guild_data = await shared_utils.get_guild_queue_info(guild_config.guild_id)
        if guild_data is None or not guild_data:
            guild: hikari.Guild | None = ctx.interaction.get_guild()
            if guild is None:
                guild: hikari.RESTGuild | None = await ctx.interaction.fetch_guild()
                assert guild is not None

            guild_data = await shared_utils.cache_guild_queue_info(guild)

        embed = hikari.Embed(
            title=localisations.get_localized_string(
                "commands.queue.info.responses.title",
                user_config.primary_language,
            ),
            description=desc.getvalue(),
            colour=EMBED_COLOR,
        )
        embed.set_author(
            name=guild_data["name"],
            icon=guild_data["icon"],
        )
        await ctx.respond(embed=embed)


@QUEUE_GROUP.register
class QueueViewCmd(
    lightbulb.SlashCommand,
    name="commands.queue.view.name",
    description="commands.queue.view.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    hooks=[early_ephemeral_defer],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/queue view",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        queued_suggestions_for_guild: list[QueuedSuggestions] = (
            await QueuedSuggestions.fetch_guild_queued_suggestions(
                guild_id=guild_config.guild_id,
            )
        )
        if not queued_suggestions_for_guild:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.queue.view.responses.empty",
                    user_config.primary_language,
                ),
            )
            return

        queued_suggestion_ids: list[str] = [qs.sID for qs in queued_suggestions_for_guild]
        pid = generate_id()
        link_id = await utils.otel.generate_trace_link_state()
        paginator = QueuedSuggestionsPaginator(
            data=queued_suggestion_ids,
            ctx=ctx,
            locale=user_config.primary_language,
            pid=pid,
            link_id=link_id,
        )
        PAGINATOR_OBJECTS.add_entry(pid, paginator)
        await ctx.respond(
            components=await paginator.format_page()  # ty:ignore[invalid-argument-type]
        )
        return

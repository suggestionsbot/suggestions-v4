import io
import logging

import hikari
import lightbulb

from bot import utils
from bot.constants import QUEUE_GROUP, EMBED_COLOR, PAGINATOR_OBJECTS
from bot.localisation import Localisation
from bot.utils import QueuedSuggestionsPaginator, generate_id
from shared.tables import (
    GuildConfigs,
    Suggestions,
    QueuedSuggestions,
    UserConfigs,
)

logger = logging.getLogger(__name__)


@QUEUE_GROUP.register
class QueueInfoCmd(
    lightbulb.SlashCommand,
    name="commands.queue.info.name",
    description="commands.queue.info.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        queued_suggestions_for_guild: list[QueuedSuggestions] = (
            await QueuedSuggestions.fetch_guild_queued_suggestions(
                guild_id=guild_config.guild_id
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
            )
        )
        desc.write("\n")
        ext = "yes" if guild_config.uses_suggestion_queue else "no"
        desc.write(
            localisations.get_localized_string(
                f"commands.queue.info.responses.description_new_queued.{ext}",
                user_config.primary_language,
            )
        )

        guild: hikari.Guild | None = ctx.interaction.get_guild()
        if guild is None:
            guild: hikari.Guild = await ctx.interaction.fetch_guild()  # TODO cache

        embed = hikari.Embed(
            title=localisations.get_localized_string(
                "commands.queue.info.responses.title", user_config.primary_language
            ),
            description=desc.getvalue(),
            colour=EMBED_COLOR,
        )
        embed.set_author(
            name=guild.name,
            icon=guild.make_icon_url(),
        )
        await ctx.respond(embed=embed)


@QUEUE_GROUP.register
class QueueViewCmd(
    lightbulb.SlashCommand,
    name="commands.queue.view.name",
    description="commands.queue.view.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        queued_suggestions_for_guild: list[QueuedSuggestions] = (
            await QueuedSuggestions.fetch_guild_queued_suggestions(
                guild_id=guild_config.guild_id
            )
        )
        if not queued_suggestions_for_guild:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.queue.view.responses.empty", user_config.primary_language
                )
            )
            return None

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
        await ctx.respond(components=await paginator.format_page())
        return None

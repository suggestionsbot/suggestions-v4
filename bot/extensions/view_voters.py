import io
import logging
from itertools import batched
from typing import cast

import hikari
import lightbulb

import shared
from bot import utils
from bot.constants import (
    VIEW_GROUP,
    PAGINATOR_OBJECTS,
    DEFAULT_UP_VOTE,
    DEFAULT_DOWN_VOTE,
)
from bot.localisation import Localisation
from bot.utils import generate_id, ViewVotersPaginator
from shared.tables import (
    GuildConfigs,
    UserConfigs,
    Suggestions,
    SuggestionStateEnum,
    QueuedSuggestions,
    QueuedSuggestionStateEnum,
    SuggestionVotes,
    SuggestionsVoteTypeEnum,
)
from web.util.table_mixins import utc_now

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = ctx.focused.value or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=ctx.interaction.guild_id,
        search=current_value,
        index="suggestion_sid_autocomplete_index",
    )
    await ctx.respond(values_to_recommend)


@VIEW_GROUP.register
class ViewVotersCmd(
    lightbulb.SlashCommand,
    name="commands.view.voters.name",
    description="commands.view.voters.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion_id = lightbulb.string(
        "commands.view.voters.options.suggestion_id.name",
        "commands.view.voters.options.suggestion_id.description",
        localize=True,
        autocomplete=autocomplete_callback,
    )
    filter_raw = lightbulb.string(
        "commands.view.voters.options.filter.name",
        "commands.view.voters.options.filter.description",
        localize=True,
        default=lightbulb.Choice(
            "commands.view.voters.options.filter.1.name",
            "All",
            True,
        ),
        choices=[
            lightbulb.Choice(
                "commands.view.voters.options.filter.1.name",
                "All",
                True,
            ),
            lightbulb.Choice(
                "commands.view.voters.options.filter.2.name",
                "Up",
                True,
            ),
            lightbulb.Choice(
                "commands.view.voters.options.filter.3.name",
                "Down",
                True,
            ),
        ],
    )

    @lightbulb.invoke
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
    ) -> None:
        await ctx.defer(ephemeral=True)
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id, guild_config.guild_id
        )
        if suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.view.voters.responses.not_found",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return None

        vote_type = (
            SuggestionsVoteTypeEnum.UpVote
            if self.filter_raw == "Up"
            else SuggestionsVoteTypeEnum.DownVote if self.filter_raw == "Down" else None
        )
        votes = await SuggestionVotes.fetch_votes_for_suggestion(
            suggestion, vote_type=vote_type
        )
        if not votes:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.view.voters.responses.no_votes",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return None

        data = []
        for group in batched(votes, 25):
            text = io.StringIO()
            for item in group:
                emoji = (
                    DEFAULT_UP_VOTE
                    if item.vote_type_enum == SuggestionsVoteTypeEnum.UpVote
                    else DEFAULT_DOWN_VOTE
                )
                text.write(f"{emoji} <@{item.user_id}>")

            data.append(text.getvalue())

        pid = generate_id()
        link_id = await utils.otel.generate_trace_link_state()
        paginator = ViewVotersPaginator(
            data=data,
            ctx=ctx,
            locale=user_config.primary_language,
            pid=pid,
            link_id=link_id,
            sid=suggestion.sID,
        )
        PAGINATOR_OBJECTS.add_entry(pid, paginator)
        await ctx.respond(components=await paginator.format_page())
        return None

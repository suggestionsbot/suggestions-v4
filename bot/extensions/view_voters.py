from typing import cast
import io
import logging
from itertools import batched

import hikari
import lightbulb

import shared.utils
from bot import utils
from bot.constants import (
    VIEW_GROUP,
    PAGINATOR_OBJECTS,
    DEFAULT_UP_VOTE,
    DEFAULT_DOWN_VOTE,
)
from bot.hooks import early_ephemeral_defer
from bot.localisation import Localisation
from bot.tables import CommandInvokes, CommandTypes
from bot.utils import generate_id, ViewVotersPaginator
from shared.tables import (
    GuildConfigs,
    UserConfigs,
    Suggestions,
    SuggestionVotes,
    SuggestionsVoteTypeEnum,
)

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


async def autocomplete_callback(ctx: lightbulb.AutocompleteContext[str]) -> None:
    current_value: str = str(ctx.focused.value) or ""
    values_to_recommend = await shared.utils.get_sid_autocomplete_for_guild(
        guild_id=cast("int", ctx.interaction.guild_id),
        search=current_value,
        index="suggestion_sid_autocomplete_index",
    )
    await ctx.respond(values_to_recommend)


async def get_vote_data(
    *,
    suggestion: Suggestions,
    vote_type: SuggestionsVoteTypeEnum | None,
    ctx: lightbulb.Context,
    localisations: Localisation,
    user_config: UserConfigs,
) -> list[str] | None:
    votes = await SuggestionVotes.fetch_votes_for_suggestion(
        suggestion,
        vote_type=vote_type,
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
            text.write(f"{emoji} <@{item.user_id}>\n")

        data.append(text.getvalue())
    return data


async def view_voters_for_suggestion(
    *,
    suggestion: Suggestions,
    data: list[str],
    ctx: lightbulb.Context,
    user_config: UserConfigs,
) -> None:
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
    await ctx.respond(
        components=await paginator.format_page()  # ty:ignore[invalid-argument-type]
    )


@VIEW_GROUP.register
class ViewVotersCmd(
    lightbulb.SlashCommand,
    name="commands.view.voters.name",
    description="commands.view.voters.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
    hooks=[early_ephemeral_defer],
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
            localize=True,
        ),
        choices=[
            lightbulb.Choice(
                "commands.view.voters.options.filter.1.name",
                "All",
                localize=True,
            ),
            lightbulb.Choice(
                "commands.view.voters.options.filter.2.name",
                "Up",
                localize=True,
            ),
            lightbulb.Choice(
                "commands.view.voters.options.filter.3.name",
                "Down",
                localize=True,
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
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="/view voters",
            command_type=CommandTypes.SLASH_COMMAND,
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion(
            self.suggestion_id,
            guild_config.guild_id,
        )
        if suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.view.voters.responses.not_found",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return

        vote_type = (
            SuggestionsVoteTypeEnum.UpVote
            if self.filter_raw == "Up"
            else SuggestionsVoteTypeEnum.DownVote if self.filter_raw == "Down" else None
        )

        data = await get_vote_data(
            suggestion=suggestion,
            ctx=ctx,
            user_config=user_config,
            vote_type=vote_type,
            localisations=localisations,
        )
        if data is None:
            return

        await view_voters_for_suggestion(
            suggestion=suggestion,
            data=data,
            ctx=ctx,
            user_config=user_config,
        )
        return


class ViewVoterMessageCommand(
    lightbulb.MessageCommand,
    name="message_commands.view_voters.name",
    localize=True,
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
        # 'self.target' contains the message object the command was executed on
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="View Voters",
            command_type=CommandTypes.MESSAGE_COMMAND,
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion_by_message(
            channel_id=self.target.channel_id,
            message_id=self.target.id,
            guild_id=guild_config.guild_id,
        )
        if suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.view.voters.responses.not_found",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return

        data = await get_vote_data(
            suggestion=suggestion,
            ctx=ctx,
            user_config=user_config,
            vote_type=None,
            localisations=localisations,
        )
        if data is None:
            return

        await view_voters_for_suggestion(
            suggestion=suggestion,
            data=data,
            ctx=ctx,
            user_config=user_config,
        )
        return


class ViewUpVoterMessageCommand(
    lightbulb.MessageCommand,
    name="message_commands.view_up_voters.name",
    localize=True,
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
        # 'self.target' contains the message object the command was executed on
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="View Up Voters",
            command_type=CommandTypes.MESSAGE_COMMAND,
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion_by_message(
            channel_id=self.target.channel_id,
            message_id=self.target.id,
            guild_id=guild_config.guild_id,
        )
        if suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.view.voters.responses.not_found",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return

        data = await get_vote_data(
            suggestion=suggestion,
            ctx=ctx,
            user_config=user_config,
            vote_type=SuggestionsVoteTypeEnum.UpVote,
            localisations=localisations,
        )
        if data is None:
            return

        await view_voters_for_suggestion(
            suggestion=suggestion,
            data=data,
            ctx=ctx,
            user_config=user_config,
        )
        return


class ViewDownVoterMessageCommand(
    lightbulb.MessageCommand,
    name="message_commands.view_down_voters.name",
    localize=True,
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
        # 'self.target' contains the message object the command was executed on
        await CommandInvokes.create(
            user_config=user_config,
            guild_config=guild_config,
            action="View Down Voters",
            command_type=CommandTypes.MESSAGE_COMMAND,
        )
        suggestion: Suggestions | None = await Suggestions.fetch_suggestion_by_message(
            channel_id=self.target.channel_id,
            message_id=self.target.id,
            guild_id=guild_config.guild_id,
        )
        if suggestion is None:
            await ctx.respond(
                localisations.get_localized_string(
                    "commands.view.voters.responses.not_found",
                    user_config.primary_language,
                ),
                ephemeral=True,
            )
            return

        data = await get_vote_data(
            suggestion=suggestion,
            ctx=ctx,
            user_config=user_config,
            vote_type=SuggestionsVoteTypeEnum.DownVote,
            localisations=localisations,
        )
        if data is None:
            return

        await view_voters_for_suggestion(
            suggestion=suggestion,
            data=data,
            ctx=ctx,
            user_config=user_config,
        )
        return

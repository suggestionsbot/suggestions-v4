import time
from typing import cast
from unittest.mock import AsyncMock

import lightbulb
import pytest
import redis.asyncio as aioredis
from freezegun import freeze_time

from bot import utils
from bot.localisation import Localisation
from bot.menus import SuggestionMenu
from bot.tables import (
    CommandInvokes,
    CommandTypes,
    MessageAddons,
    PossibleMessageAddons,
)
from shared.tables import (
    GuildConfigs,
    SuggestionStateEnum,
    Suggestions,
    SuggestionsVoteTypeEnum,
    SuggestionVotes,
    UserConfigs,
)
from shared.utils import configs

USER_ID = 12345
GUILD_ID = 23456
DISPLAY_NAME = "Skelmis"
SID = "aaaa1111"

UP_VOTE_REGISTERED = "Thanks!\nI have registered your up vote."
DOWN_VOTE_REGISTERED = "Thanks!\nI have registered your down vote."
UP_VOTE_ALREADY_VOTED = "You have already up voted this suggestion."
DOWN_VOTE_ALREADY_VOTED = "You have already down voted this suggestion."
CHANGED_TO_DOWN_VOTE = (
    "I have changed your vote from an up vote to a down vote for this suggestion.\n"
    "The suggestion will be updated shortly."
)
CHANGED_TO_UP_VOTE = (
    "I have changed your vote from a down vote to an up vote for this suggestion.\n"
    "The suggestion will be updated shortly."
)
NO_MORE_CASTING = "You can no longer cast votes on this suggestion."
NOT_FOUND_TITLE = "Suggestion Not Found."
NOT_FOUND_DESCRIPTION = (
    "This suggestion could not be found as it likely no longer exists."
)
MISSING_PERMS_MESSAGE = (
    "I have recorded your vote successfully however I am reaching out to also "
    "inform you that I have failed to edit a suggestion in the last few hours. "
    "Please ask a server admin to double check that I have all the required "
    "permissions in the channel otherwise you may see suggestions without votes."
    "\n\nPermissions can be found here: <https://docs.suggestions.gg/docs/intro>"
)


def create_context(user_id: int = USER_ID, guild_id: int = GUILD_ID) -> AsyncMock:
    """Builds a mocked menu context for the given user."""
    ctx = AsyncMock(spec=lightbulb.components.MenuContext)
    ctx.interaction.locale = "en-GB"
    ctx.user.id = user_id
    ctx.user.display_name = DISPLAY_NAME
    ctx.guild_id = guild_id
    return ctx


async def suppress_message_addon(user_id: int = USER_ID) -> None:
    """Marks the user as recently shown an addon so responses stay exact.

    Addons are otherwise appended to every vote response, and which one is
    picked is not this method's concern - see `test_message_addon_is_appended`.
    """
    user_config = await configs.ensure_user_config(user_id)
    await MessageAddons(
        shown_message=PossibleMessageAddons.READ_CHANGELOG,
        user=user_config,
    ).save()


async def create_suggestion(
    *,
    sid: str = SID,
    guild_id: int = GUILD_ID,
    user_id: int = USER_ID,
    state: SuggestionStateEnum = SuggestionStateEnum.PENDING,
    suppress_addon: bool = True,
) -> tuple[Suggestions, GuildConfigs, UserConfigs]:
    """Persists a suggestion which can then be voted upon."""
    guild_config = await configs.ensure_guild_config(guild_id)
    user_config = await configs.ensure_user_config(user_id)
    if suppress_addon:
        await suppress_message_addon(user_id)

    suggestion = Suggestions(
        guild_configuration=guild_config,
        user_configuration=user_config,
        suggestion="test",
        author_display_name=DISPLAY_NAME,
        state_raw=state.value,
        sID=sid,
    )
    await suggestion.save()
    return suggestion, guild_config, user_config


async def invoke_vote(
    localisations: Localisation,
    vote: SuggestionsVoteTypeEnum = SuggestionsVoteTypeEnum.UpVote,
    *,
    sid: str = SID,
    user_id: int = USER_ID,
    guild_id: int = GUILD_ID,
) -> AsyncMock:
    """Presses an up or down vote button as the given user."""
    ctx = create_context(user_id, guild_id)
    await SuggestionMenu.handle_vote(
        sid,
        vote,
        ctx=cast("lightbulb.components.MenuContext", ctx),
        localisations=localisations,
    )
    return ctx


def responded_content(ctx: AsyncMock) -> str:
    """Returns the content the single ephemeral response was sent with."""
    ctx.respond.assert_called_once()
    args, kwargs = ctx.respond.call_args
    assert kwargs["ephemeral"] is True, "Expected vote responses to be ephemeral"
    return args[0]


@freeze_time("2025-01-20")
async def test_suggestion_not_found(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts voting on a suggestion which doesn't exist is handled."""
    await create_suggestion()
    ctx = await invoke_vote(localisation, sid="not-a-real-sid")

    ctx.defer.assert_called_once_with(ephemeral=True)
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(NOT_FOUND_TITLE, NOT_FOUND_DESCRIPTION),
        ephemeral=True,
    )
    assert await SuggestionVotes.count() == 0


@freeze_time("2025-01-20")
async def test_suggestion_in_another_guild_is_not_found(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts a suggestion can only be voted on from within its own guild."""
    await create_suggestion()
    ctx = await invoke_vote(localisation, guild_id=GUILD_ID + 1)

    assert await SuggestionVotes.count() == 0, (
        "Expected no vote to be cast against another guild's suggestion"
    )
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(NOT_FOUND_TITLE, NOT_FOUND_DESCRIPTION),
        ephemeral=True,
    )


@pytest.mark.parametrize(
    "state",
    [
        SuggestionStateEnum.APPROVED,
        SuggestionStateEnum.REJECTED,
        SuggestionStateEnum.CLEARED,
        SuggestionStateEnum.IMPLEMENTED,
        SuggestionStateEnum.DUPLICATE,
    ],
)
async def test_resolved_suggestions_cant_be_voted_on(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    state: SuggestionStateEnum,
) -> None:
    """Asserts votes are rejected once a suggestion is no longer pending."""
    await create_suggestion(state=state)
    ctx = await invoke_vote(localisation)

    assert responded_content(ctx) == NO_MORE_CASTING
    assert await SuggestionVotes.count() == 0


async def test_tracks_command_invoke(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts casting a vote is tracked as a button invoke."""
    _, guild_config, _ = await create_suggestion()
    ctx = await invoke_vote(localisation)

    assert responded_content(ctx) == UP_VOTE_REGISTERED

    invoke = await CommandInvokes.objects().first()
    assert invoke is not None
    assert invoke.action == "Suggestion Vote"
    assert invoke.action_type == CommandTypes.BUTTON
    assert invoke.user_id == USER_ID
    assert invoke.guild_id == GUILD_ID
    assert invoke.guild_locale == guild_config.primary_language.value


@pytest.mark.parametrize(
    ("vote", "expected_message"),
    [
        (SuggestionsVoteTypeEnum.UpVote, UP_VOTE_REGISTERED),
        (SuggestionsVoteTypeEnum.DownVote, DOWN_VOTE_REGISTERED),
    ],
)
async def test_new_vote_is_registered(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    vote: SuggestionsVoteTypeEnum,
    expected_message: str,
) -> None:
    """Asserts a first time vote is stored and confirmed to the user."""
    suggestion, _, _ = await create_suggestion()
    ctx = await invoke_vote(localisation, vote)

    assert responded_content(ctx) == expected_message

    vote_obj = await SuggestionVotes.objects().first()
    assert vote_obj is not None
    assert vote_obj.vote_type_enum == vote
    assert vote_obj.user_id == USER_ID
    assert vote_obj.suggestion == suggestion.id
    assert vote_obj.voter_display_name_raw == f"{DISPLAY_NAME} (<@{USER_ID}>)"


@freeze_time("2025-01-20")
async def test_queues_a_message_edit(
    localisation: Localisation,
    patch_saq: AsyncMock,
) -> None:
    """Asserts the suggestion message is queued for an update after a vote."""
    await create_suggestion()
    ctx = await invoke_vote(localisation)

    assert responded_content(ctx) == UP_VOTE_REGISTERED
    patch_saq.assert_called_once()
    patch_saq.assert_called_once_with(
        "edit_suggestion_message",
        suggestion_id=SID,
        guild_id=GUILD_ID,
        exclude_buttons=False,
        as_resolved=False,
        # The edit is deliberately delayed so votes cast together batch up
        scheduled=time.time() + 10,
    )


@pytest.mark.parametrize(
    ("vote", "expected_message"),
    [
        (SuggestionsVoteTypeEnum.UpVote, UP_VOTE_ALREADY_VOTED),
        (SuggestionsVoteTypeEnum.DownVote, DOWN_VOTE_ALREADY_VOTED),
    ],
)
async def test_voting_twice_the_same_way(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    vote: SuggestionsVoteTypeEnum,
    expected_message: str,
) -> None:
    """Asserts recasting the same vote tells the user rather than duplicating."""
    await create_suggestion()
    await invoke_vote(localisation, vote)
    ctx = await invoke_vote(localisation, vote)

    assert responded_content(ctx) == expected_message
    assert await SuggestionVotes.count() == 1


@pytest.mark.parametrize(
    ("initial_vote", "new_vote", "expected_message"),
    [
        (
            SuggestionsVoteTypeEnum.UpVote,
            SuggestionsVoteTypeEnum.DownVote,
            CHANGED_TO_DOWN_VOTE,
        ),
        (
            SuggestionsVoteTypeEnum.DownVote,
            SuggestionsVoteTypeEnum.UpVote,
            CHANGED_TO_UP_VOTE,
        ),
    ],
)
async def test_changing_a_vote(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    initial_vote: SuggestionsVoteTypeEnum,
    new_vote: SuggestionsVoteTypeEnum,
    expected_message: str,
) -> None:
    """Asserts a vote can be switched without creating a second vote."""
    await create_suggestion()
    await invoke_vote(localisation, initial_vote)
    assert await SuggestionVotes.count() == 1
    vote_obj = await SuggestionVotes.objects().first()
    assert vote_obj is not None
    assert vote_obj.vote_type_enum == initial_vote

    ctx = await invoke_vote(localisation, new_vote)

    assert responded_content(ctx) == expected_message
    assert await SuggestionVotes.count() == 1
    vote_obj = await SuggestionVotes.objects().first()
    assert vote_obj is not None
    assert vote_obj.vote_type_enum == new_vote


async def test_votes_are_per_user(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts each user gets their own vote on a suggestion."""
    await create_suggestion()
    await invoke_vote(localisation, SuggestionsVoteTypeEnum.UpVote)

    await suppress_message_addon(USER_ID + 1)  # Also creates a user for us
    ctx = await invoke_vote(
        localisation, SuggestionsVoteTypeEnum.UpVote, user_id=USER_ID + 1
    )

    assert responded_content(ctx) == UP_VOTE_REGISTERED
    expected_votes = 2
    assert await SuggestionVotes.count() == expected_votes


async def test_warns_about_recent_permission_issues(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    redis_client: aioredis.Redis,
) -> None:
    """Asserts users are told when the bot recently failed to edit suggestions."""
    await create_suggestion()
    key = f"errors:missing_suggestion_perms:{GUILD_ID}"
    await redis_client.set(key, "1", ex=60)

    ctx = await invoke_vote(localisation)

    content = responded_content(ctx)
    assert content == f"{UP_VOTE_REGISTERED}\n\n{MISSING_PERMS_MESSAGE}"
    assert await redis_client.get(key) is None, (
        "Expected the warning to only be shown once"
    )


async def test_message_addon_is_appended(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
) -> None:
    """Asserts vote responses carry a message addon when one is due."""
    await create_suggestion(suppress_addon=False)
    ctx = await invoke_vote(localisation)

    addon = await MessageAddons.objects(MessageAddons.user).first()
    assert addon is not None, "Expected an addon to be shown alongside the vote"
    assert responded_content(ctx) == f"{UP_VOTE_REGISTERED}\n\n{await addon.as_string()}"


async def test_permission_warning_and_addon_together(
    localisation: Localisation,
    patch_saq: AsyncMock,  # noqa: ARG001
    redis_client: aioredis.Redis,
) -> None:
    """Asserts a permissions warning and an addon can share one response."""
    await create_suggestion(suppress_addon=False)
    key = f"errors:missing_suggestion_perms:{GUILD_ID}"
    await redis_client.set(key, "1", ex=60)

    ctx = await invoke_vote(localisation)

    addon = await MessageAddons.objects(MessageAddons.user).first()
    assert addon is not None, "Expected an addon to be shown alongside the vote"
    assert responded_content(ctx) == (
        f"{UP_VOTE_REGISTERED}\n\n{MISSING_PERMS_MESSAGE}\n\n{await addon.as_string()}"
    )

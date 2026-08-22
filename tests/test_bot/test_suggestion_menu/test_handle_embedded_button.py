from typing import cast
from unittest.mock import AsyncMock, _Call

import hikari
import lightbulb
import pytest
from freezegun import freeze_time
import redis.asyncio as aioredis

from bot import utils
from bot.constants import ErrorCode
from bot.localisation import Localisation
from bot.menus import SuggestionMenu
from bot.tables import CommandInvokes, CommandTypes
from shared.tables import GuildConfigs
from shared.utils import configs

USER_ID = 12345
GUILD_ID = 23456
CHANNEL_ID = 348934


def create_context(user_id: int = USER_ID, guild_id: int = GUILD_ID) -> AsyncMock:
    """Builds a mocked menu context for the given user."""
    ctx = AsyncMock(spec=lightbulb.components.MenuContext)
    ctx.interaction.locale = "en-GB"
    # `interaction` is a property, so its children aren't async by default
    ctx.interaction.create_modal_response = AsyncMock()
    ctx.user.id = user_id
    ctx.guild_id = guild_id
    return ctx


async def invoke_button(
    localisations: Localisation,
    user_id: int = USER_ID,
    guild_id: int = GUILD_ID,
    *,
    guild_config: GuildConfigs | None = None,
) -> tuple[AsyncMock, GuildConfigs]:
    """Presses the embedded suggest button as the given user."""
    if guild_config is None:
        guild_config = await configs.ensure_guild_config(guild_id)
        guild_config.suggestions_channel_id = CHANNEL_ID

    await guild_config.save()

    ctx = create_context(user_id, guild_id)
    await SuggestionMenu.handle_embedded_button(
        ctx=cast("lightbulb.components.MenuContext", ctx),
        localisations=localisations,
    )
    return ctx, guild_config


def get_modal_call_args(ctx: AsyncMock) -> _Call:
    """Returns the args the modal was opened with, asserting it was opened once."""
    ctx.interaction.create_modal_response.assert_called_once()
    return ctx.interaction.create_modal_response.call_args


def get_modal_custom_ids(ctx: AsyncMock) -> list[str]:
    """Returns the custom ids of each field within the opened modal."""
    _, kwargs = get_modal_call_args(ctx)
    return [c.component.custom_id for c in kwargs["components"]]


@freeze_time("2025-01-20")
async def test_requires_setup(
    localisation: Localisation,
    redis_client: aioredis.Redis,  # noqa: ARG001
) -> None:
    """Asserts guilds without a suggestions channel get told to run setup."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.suggestions_channel_id = None
    ctx, _ = await invoke_button(localisation, guild_config=gc)

    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(
            title="Missing bot configuration",
            description="The bot requires further configuration to setup.\n"
            "Please get an administrator to run `/setup` and complete the "
            "provided form before redoing this action.",
            error_code=ErrorCode.BOT_NOT_CONFIGURED,
        ),
        ephemeral=True,
    )
    ctx.interaction.create_modal_response.assert_not_called()
    assert await CommandInvokes.count() == 0, (
        "Expected no invoke to be tracked for a guild which bailed on setup"
    )


async def test_missing_log_channel_is_skipped(
    localisation: Localisation,
    redis_client: aioredis.Redis,  # noqa: ARG001
) -> None:
    """Asserts a missing log channel does not block the suggest button."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.suggestions_channel_id = CHANNEL_ID
    gc.log_channel_id = None
    ctx, _ = await invoke_button(localisation, guild_config=gc)

    ctx.respond.assert_not_called()
    ctx.interaction.create_modal_response.assert_called_once()
    assert await CommandInvokes.count() == 1, (
        "Expected an invoke to be tracked for a guild"
    )


async def test_tracks_command_invoke(
    localisation: Localisation,
    redis_client: aioredis.Redis,  # noqa: ARG001
) -> None:
    """Asserts pressing the button is tracked as a button invoke."""
    _, gc = await invoke_button(localisation)

    invoke = await CommandInvokes.objects().first()
    assert invoke is not None
    assert invoke.action == "Create Suggestion"
    assert invoke.action_type == CommandTypes.BUTTON
    assert invoke.user_id == USER_ID
    assert invoke.guild_id == GUILD_ID
    assert invoke.guild_locale == gc.primary_language.value


async def test_modal_response(
    localisation: Localisation,
    redis_client: aioredis.Redis,
) -> None:
    """Asserts the modal is opened with a traceable custom id."""
    ctx, _ = await invoke_button(localisation)
    args, kwargs = get_modal_call_args(ctx)

    title, custom_id = args
    assert title == "Create Suggestion"
    assert custom_id.startswith("suggest_modal:")

    link_id = custom_id.split(":", maxsplit=1)[1]
    assert link_id, "Expected a trace link id in the modal custom id"
    assert await redis_client.get(f"trace_context:{link_id}") is not None, (
        "Expected the trace context to be persisted for the modal to pick up"
    )
    assert kwargs["components"]


async def test_default_modal_components(
    localisation: Localisation,
    redis_client: aioredis.Redis,  # noqa: ARG001
) -> None:
    """Asserts a default guild config gets every modal field."""
    ctx, _ = await invoke_button(localisation)

    assert get_modal_custom_ids(ctx) == [
        "suggestion",
        "files",
        "anonymously",
        "thread_name",
    ]


@pytest.mark.parametrize(
    ("images", "anonymous", "threads", "expected", "message"),
    [
        (
            False,
            False,
            False,
            ["suggestion"],
            "Expected only the suggestion field when all extras are disabled",
        ),
        (
            True,
            False,
            False,
            ["suggestion", "files"],
            "Expected the file upload when images are enabled",
        ),
        (
            False,
            True,
            False,
            ["suggestion", "anonymously"],
            "Expected the anonymous select when anonymous suggestions are enabled",
        ),
        (
            False,
            False,
            True,
            ["suggestion", "thread_name"],
            "Expected the thread name field when threads are enabled",
        ),
    ],
)
async def test_modal_components_follow_guild_config(
    localisation: Localisation,
    redis_client: aioredis.Redis,  # noqa: ARG001
    images: bool,
    anonymous: bool,
    threads: bool,
    expected: list[str],
    message: str,
) -> None:
    """Asserts the modal only offers the fields the guild has enabled."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.suggestions_channel_id = CHANNEL_ID
    gc.can_have_images_in_suggestions = images
    gc.can_have_anonymous_suggestions = anonymous
    gc.threads_for_suggestions = threads
    ctx, _ = await invoke_button(localisation, guild_config=gc)

    assert get_modal_custom_ids(ctx) == expected, message


async def test_suggestion_field_is_required(
    localisation: Localisation,
    redis_client: aioredis.Redis,  # noqa: ARG001
) -> None:
    """Asserts the suggestion input itself cannot be skipped by the user."""
    ctx, _ = await invoke_button(localisation)
    _, kwargs = get_modal_call_args(ctx)

    suggestion = kwargs["components"][0].component
    assert suggestion.custom_id == "suggestion"
    assert suggestion.is_required is True
    assert suggestion.style == hikari.TextInputStyle.PARAGRAPH


@freeze_time("2025-01-20")
async def test_creates_configs_for_unseen_guild(
    localisation: Localisation,
    redis_client: aioredis.Redis,  # noqa: ARG001
) -> None:
    """Asserts guilds we have never seen before get a config on first press."""
    guild_id = 888
    user_id = 999
    ctx = create_context(user_id, guild_id)

    await SuggestionMenu.handle_embedded_button(
        ctx=cast("lightbulb.components.MenuContext", ctx),
        localisations=localisation,
    )

    gc = await GuildConfigs.objects().first().where(GuildConfigs.guild_id == guild_id)
    assert gc is not None, "Expected a guild config to be created by the button press"
    # Unconfigured guild, so we expect the setup message rather than a modal
    ctx.interaction.create_modal_response.assert_not_called()
    ctx.respond.assert_called_once_with(
        embed=utils.error_embed(
            title="Missing bot configuration",
            description="The bot requires further configuration to setup.\n"
            "Please get an administrator to run `/setup` and complete the "
            "provided form before redoing this action.",
            error_code=ErrorCode.BOT_NOT_CONFIGURED,
        ),
        ephemeral=True,
    )

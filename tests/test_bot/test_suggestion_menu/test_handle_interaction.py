import logging
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, Mock

import hikari
import lightbulb
import pytest
from freezegun import freeze_time

from bot import utils
from bot.constants import MAX_CONTENT_LENGTH, ErrorCode
from bot.exceptions import InvalidFileType
from bot.localisation import Localisation
from bot.menus import SuggestionMenu
from shared.tables import GuildConfigs, Suggestions, UserConfigs
from shared.utils import configs, r2

if TYPE_CHECKING:
    from hikari.interactions.interaction_components import LabelInteractionComponent

USER_ID = 12345
GUILD_ID = 23456
DISPLAY_NAME = "Skelmis"
IMAGE_URL = "https://example.com/fake_image_url"
SUGGESTION_MENU_LOGGER = "bot.menus.suggestion_menu"

NO_IMAGES = "Your guild does not allow images in suggestions."
NO_ANONYMOUS = "Your guild does not allow anonymous suggestions."
BAD_FILE_TYPE = (
    "We only allow image like files in suggestion uploads and it looks like one "
    "of your images did not meet our criteria.\nPlease try again with one of the "
    "following files:`.jpeg`, `.jpg`, `.png`, `.mp3`, `.mp4`, `.gif`"
)
CONTENT_TOO_LONG_TITLE = "Command Failed"
CONTENT_TOO_LONG_DESCRIPTION = (
    f"Your content was too long, please limit it to {MAX_CONTENT_LENGTH} "
    "characters or less.\n\nI have attached a file containing your content "
    "to save rewriting it entirely."
)


def label(custom_id: str, **attributes: Any) -> Mock:  # noqa: ANN401
    """Builds a single modal field as it arrives back from discord."""
    return Mock(component=Mock(custom_id=custom_id, **attributes))


def create_fields(
    suggestion: str = "test",
    *,
    anonymously: str | None = None,
    thread_name: str | None = None,
    file_ids: list[hikari.Snowflake] | None = None,
) -> list[Mock]:
    """Builds the modal response for the fields the guild had enabled."""
    fields = [label("suggestion", value=suggestion)]
    if file_ids is not None:
        fields.append(label("files", values=file_ids))

    if anonymously is not None:
        fields.append(label("anonymously", values=[anonymously]))

    if thread_name is not None:
        fields.append(label("thread_name", value=thread_name))

    return fields


def create_context() -> AsyncMock:
    """Builds a mocked menu context for the suggesting user."""
    ctx = AsyncMock(spec=lightbulb.components.MenuContext)
    ctx.interaction.locale = "en-GB"
    ctx.user.id = USER_ID
    ctx.user.display_name = DISPLAY_NAME
    ctx.guild_id = GUILD_ID
    return ctx


def create_event(attachments: dict[hikari.Snowflake, Any] | None = None) -> AsyncMock:
    """Builds the modal event, resolving any attachments the user uploaded."""
    event = AsyncMock()
    event.interaction.resolved.attachments = attachments or {}
    return event


def create_attachment(filename: str = "content.png", data: bytes = b"test") -> AsyncMock:
    attachment = AsyncMock(spec=hikari.messages.Attachment)
    attachment.filename = filename
    attachment.read.return_value = data
    return attachment


async def invoke_interaction(
    localisations: Localisation,
    fields: list[Mock],
    *,
    guild_config: GuildConfigs | None = None,
    event: AsyncMock | None = None,
) -> tuple[AsyncMock, Suggestions | None, GuildConfigs, UserConfigs]:
    """Submits the suggest modal with the given fields."""
    if guild_config is None:
        guild_config = await configs.ensure_guild_config(GUILD_ID)

    user_config = await configs.ensure_user_config(USER_ID)
    await guild_config.save()

    ctx = create_context()
    result = await SuggestionMenu.handle_interaction(
        cast("list[LabelInteractionComponent]", fields),
        ctx=cast("lightbulb.components.MenuContext", ctx),
        localisations=localisations,
        guild_config=guild_config,
        user_config=user_config,
        event=cast("hikari.ModalInteractionCreateEvent", event or create_event()),
    )
    return ctx, result, guild_config, user_config


def responded_content(ctx: AsyncMock) -> str:
    """Returns the content the single ephemeral response was sent with."""
    ctx.respond.assert_called_once()
    args, kwargs = ctx.respond.call_args
    assert kwargs["ephemeral"] is True, "Expected modal errors to be ephemeral"
    return args[0]


@pytest.fixture
def patch_handle_suggestion(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Stubs the delegate so these tests only cover the modal handling."""
    handle_suggestion = AsyncMock(return_value=Mock(spec=Suggestions))
    monkeypatch.setattr(SuggestionMenu, "handle_suggestion", handle_suggestion)
    return handle_suggestion


@pytest.fixture
def patch_handle_queued_suggestion(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Stubs the queued delegate so these tests only cover the modal handling."""
    handle_queued = AsyncMock(return_value=None)
    monkeypatch.setattr(SuggestionMenu, "handle_queued_suggestion", handle_queued)
    return handle_queued


@pytest.fixture
def patch_r2(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Stops image uploads from leaving the test."""
    upload = AsyncMock(return_value=IMAGE_URL)
    monkeypatch.setattr(r2, "upload_file_to_r2", upload)
    return upload


async def test_delegates_to_handle_suggestion(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
) -> None:
    """Asserts a plain suggestion is handed off with the modal contents."""
    ctx, result, guild_config, user_config = await invoke_interaction(
        localisation, create_fields("test")
    )

    ctx.respond.assert_not_called()
    patch_handle_suggestion.assert_called_once_with(
        suggestion="test",
        image_urls=[],
        author_display_name=f"{DISPLAY_NAME} (<@{USER_ID}>)",
        ctx=ctx,
        guild_config=guild_config,
        user_config=user_config,
        localisations=localisation,
        thread_name=None,
    )


async def test_delegates_to_handle_queued_suggestion(
    localisation: Localisation,
    patch_handle_queued_suggestion: AsyncMock,
) -> None:
    """Asserts guilds using the queue hand off to the queued delegate."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.uses_suggestion_queue = True
    ctx, result, guild_config, user_config = await invoke_interaction(
        localisation, create_fields("test"), guild_config=gc
    )

    patch_handle_queued_suggestion.assert_called_once_with(
        suggestion="test",
        image_urls=[],
        is_anonymous=False,
        ctx=ctx,
        guild_config=guild_config,
        user_config=user_config,
        localisations=localisation,
    )


async def test_thread_name_is_passed_on(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
) -> None:
    """Asserts a user supplied thread name reaches the delegate."""
    await invoke_interaction(localisation, create_fields("test", thread_name="a thread"))

    _, kwargs = patch_handle_suggestion.call_args
    assert kwargs["thread_name"] == "a thread"


async def test_blank_thread_name_is_ignored(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
) -> None:
    """Asserts an empty thread name falls back to the default one."""
    await invoke_interaction(localisation, create_fields("test", thread_name=""))

    _, kwargs = patch_handle_suggestion.call_args
    assert kwargs["thread_name"] is None


@pytest.mark.parametrize(
    ("value", "expected_name"),
    [
        ("yes", "Anonymous"),
        ("no", f"{DISPLAY_NAME} (<@{USER_ID}>)"),
    ],
)
async def test_anonymous_selection(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
    value: str,
    expected_name: str,
) -> None:
    """Asserts the anonymous choice decides the displayed author."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.can_have_anonymous_suggestions = True
    await invoke_interaction(
        localisation, create_fields("test", anonymously=value), guild_config=gc
    )

    _, kwargs = patch_handle_suggestion.call_args
    assert kwargs["author_display_name"] == expected_name


async def test_anonymous_when_disabled(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
) -> None:
    """Asserts anonymous suggestions are refused when the guild disallows them."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.can_have_anonymous_suggestions = False
    ctx, result, _, _ = await invoke_interaction(
        localisation, create_fields("test", anonymously="yes"), guild_config=gc
    )

    assert responded_content(ctx) == NO_ANONYMOUS
    assert result is None
    patch_handle_suggestion.assert_not_called()


async def test_images_when_disabled(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
    patch_r2: AsyncMock,
) -> None:
    """Asserts images are refused when the guild disallows them."""
    gc = await configs.ensure_guild_config(GUILD_ID)
    gc.can_have_images_in_suggestions = False
    ctx, result, _, _ = await invoke_interaction(
        localisation,
        create_fields("test", file_ids=[hikari.Snowflake(1)]),
        guild_config=gc,
    )

    assert responded_content(ctx) == NO_IMAGES
    assert result is None
    patch_r2.assert_not_called()
    patch_handle_suggestion.assert_not_called()


async def test_images_are_uploaded(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
    patch_r2: AsyncMock,
) -> None:
    """Asserts uploaded images are stored and handed on to the delegate."""
    file_id = hikari.Snowflake(1)
    attachment = create_attachment()
    await invoke_interaction(
        localisation,
        create_fields("test", file_ids=[file_id]),
        event=create_event({file_id: attachment}),
    )

    patch_r2.assert_called_once_with(
        file_name="content.png",
        file_data=b"test",
        guild_id=GUILD_ID,
        user_id=USER_ID,
    )
    _, kwargs = patch_handle_suggestion.call_args
    assert kwargs["image_urls"] == [IMAGE_URL]


async def test_unresolvable_attachment_is_skipped(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
    patch_r2: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Asserts an image discord didn't resolve doesn't sink the suggestion."""
    with caplog.at_level(logging.CRITICAL, logger=SUGGESTION_MENU_LOGGER):
        await invoke_interaction(
            localisation,
            create_fields("test", file_ids=[hikari.Snowflake(1)]),
            event=create_event(),
        )

    assert [
        record.getMessage()
        for record in caplog.records
        if record.name == SUGGESTION_MENU_LOGGER
    ] == ["failed to find an image in the resolved attachments"]
    patch_r2.assert_not_called()
    _, kwargs = patch_handle_suggestion.call_args
    assert kwargs["image_urls"] == []


async def test_bad_file_type(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
    patch_r2: AsyncMock,
) -> None:
    """Asserts a rejected file type stops the suggestion with an explanation."""
    patch_r2.side_effect = InvalidFileType
    file_id = hikari.Snowflake(1)
    ctx, result, _, _ = await invoke_interaction(
        localisation,
        create_fields("test", file_ids=[file_id]),
        event=create_event({file_id: create_attachment("content.txt")}),
    )

    assert responded_content(ctx) == BAD_FILE_TYPE
    assert result is None
    patch_handle_suggestion.assert_not_called()


@freeze_time("2025-01-20")
async def test_content_too_long(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
) -> None:
    """Asserts over long suggestions come back with the content attached."""
    content = "a" * (MAX_CONTENT_LENGTH + 1)
    ctx, result, _, _ = await invoke_interaction(localisation, create_fields(content))

    ctx.respond.assert_called_once()
    _, kwargs = ctx.respond.call_args
    assert kwargs["embed"] == utils.error_embed(
        CONTENT_TOO_LONG_TITLE,
        CONTENT_TOO_LONG_DESCRIPTION,
        error_code=ErrorCode.SUGGESTION_CONTENT_TOO_LONG,
    )
    assert kwargs["ephemeral"] is True
    assert kwargs["attachment"].filename == "content.txt", (
        "Expected the content back as a file so it doesn't need rewriting"
    )
    assert result is None
    patch_handle_suggestion.assert_not_called()


async def test_content_on_the_limit_is_allowed(
    localisation: Localisation,
    patch_handle_suggestion: AsyncMock,
) -> None:
    """Asserts the length check is off by one in the user's favour."""
    content = "a" * MAX_CONTENT_LENGTH
    ctx, _, _, _ = await invoke_interaction(localisation, create_fields(content))

    ctx.respond.assert_not_called()
    _, kwargs = patch_handle_suggestion.call_args
    assert kwargs["suggestion"] == content

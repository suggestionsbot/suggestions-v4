import asyncio
import io
import logging
from typing import cast

import hikari
import lightbulb
from hikari.impl import MessageActionRowBuilder

import shared
from bot import utils
from bot.constants import ErrorCode, MAX_CONTENT_LENGTH
from bot.exceptions import MessageTooLong, MissingQueueChannel
from bot.localisation import Localisation
from bot.tables import InternalErrors
from shared.tables import GuildConfigs, UserConfigs, QueuedSuggestions

loader = lightbulb.Loader()
logger = logging.getLogger(__name__)


def handle_suggestions_errors(func):
    func = lightbulb.di.with_di(func)

    async def _wrapper(
        command_data,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ):
        try:
            return await func(
                command_data,
                ctx=ctx,
                bot=bot,
                guild_config=guild_config,
                user_config=user_config,
                localisations=localisations,
            )
        except Exception as exception:
            this_will_handle: tuple[type[Exception], ...] = (
                MessageTooLong,
                MissingQueueChannel,
            )
            if isinstance(exception, this_will_handle):
                with utils.start_error_span(exception, "command error handler"):
                    internal_error: InternalErrors = await InternalErrors.persist_error(
                        exception,
                        command_name="suggest",
                        guild_id=ctx.guild_id,
                        user_id=ctx.user.id,
                    )

                    if isinstance(exception, MessageTooLong):
                        await ctx.respond(
                            embed=utils.error_embed(
                                localisations.get_localized_string(
                                    "errors.suggest.content_too_long.title",
                                    ctx=ctx,
                                ),
                                localisations.get_localized_string(
                                    "errors.suggest.content_too_long.description",
                                    ctx=ctx,
                                    extras={"MAX_CONTENT_LENGTH": MAX_CONTENT_LENGTH},
                                ),
                                error_code=ErrorCode.SUGGESTION_CONTENT_TOO_LONG,
                                internal_error_reference=internal_error,
                            ),
                            attachment=hikari.files.Bytes(
                                io.StringIO(exception.message_text), "content.txt"
                            ),
                        )
                        return None

                    elif isinstance(exception, MissingQueueChannel):
                        await ctx.respond(
                            embed=utils.error_embed(
                                localisations.get_localized_string(
                                    "errors.suggest.missing_queue_channel.title",
                                    ctx=ctx,
                                ),
                                localisations.get_localized_string(
                                    "errors.suggest.missing_queue_channel.description",
                                    ctx=ctx,
                                ),
                                error_code=ErrorCode.MISSING_QUEUE_CHANNEL,
                                internal_error_reference=internal_error,
                            ),
                        )
                        return None

            raise

    return _wrapper


@loader.command
class Suggest(
    lightbulb.SlashCommand,
    name="commands.suggest.name",
    description="commands.suggest.description",
    localize=True,
    contexts=[hikari.ApplicationContextType.GUILD],
):
    suggestion = lightbulb.string(
        "commands.suggest.options.suggestion.name",
        "commands.suggest.options.suggestion.description",
        localize=True,
    )
    image = lightbulb.attachment(
        "commands.suggest.options.image.name",
        "commands.suggest.options.image.description",
        default=None,
        localize=True,
    )
    anonymously = lightbulb.boolean(
        "commands.suggest.options.anonymously.name",
        "commands.suggest.options.anonymously.description",
        default=False,
        localize=True,
    )

    @lightbulb.invoke
    @handle_suggestions_errors
    async def invoke(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ) -> None:
        await ctx.defer(ephemeral=True)
        if len(self.suggestion) > MAX_CONTENT_LENGTH:
            raise MessageTooLong(self.suggestion)

        if (
            self.anonymously is True
            and guild_config.can_have_anonymous_suggestions is False
        ):
            await ctx.respond(
                localisations.get_localized_string(
                    "values.suggest.no_anonymous_suggestions", ctx
                )
            )
            return None

        image_url: str | None = None
        if self.image is not None:
            if guild_config.can_have_images_in_suggestions is False:
                await ctx.respond(
                    localisations.get_localized_string(
                        "values.suggest.no_images_in_suggestions", ctx
                    )
                )
                return None

            image_url = await shared.utils.upload_file_to_r2(
                file_name=self.image.filename,
                file_data=await self.image.read(),
                guild_id=ctx.guild_id,
                user_id=ctx.user.id,
            )

        if guild_config.uses_suggestions_queue:
            return await self.handle_queued_suggestion(
                ctx, guild_config, user_config, localisations, image_url, bot
            )

        # TODO Implement more
        await asyncio.sleep(5)
        raise ValueError("Who knows")

    async def handle_queued_suggestion(
        self,
        ctx: lightbulb.Context,
        guild_config: GuildConfigs,
        user_config: UserConfigs,
        localisations: Localisation,
        image_url: str | None,
        bot: hikari.RESTBot | hikari.GatewayBot,
    ):
        """Specific helper for handling queued suggestions"""
        qs: QueuedSuggestions = QueuedSuggestions(
            guild_configuration=guild_config,
            user_configuration=user_config,
            suggestion=self.suggestion,
            image_url=image_url,
            author_display_name=(
                f"<@{ctx.user.id}>" if self.anonymously is False else "Anonymous"
            ),
        )

        if guild_config.virtual_suggestions_queue is False:
            # Need to send to a channel
            if guild_config.queued_suggestion_channel_id is None:
                raise MissingQueueChannel

            try:
                channel = await bot.rest.fetch_channel(
                    guild_config.queued_suggestion_channel_id
                )
                channel = cast(hikari.GuildTextChannel, channel)
            except (hikari.ForbiddenError, hikari.NotFoundError):
                await ctx.respond(
                    embed=utils.error_embed(
                        localisations.get_localized_string(
                            "errors.suggest.queue_channel_not_found.title",
                            ctx=ctx,
                        ),
                        localisations.get_localized_string(
                            "errors.suggest.queue_channel_not_found.description",
                            ctx=ctx,
                            extras={"MAX_CONTENT_LENGTH": MAX_CONTENT_LENGTH},
                        ),
                        error_code=ErrorCode.MISSING_PERMISSIONS_IN_QUEUE_CHANNEL,
                    ),
                )
                return None

            prefix = (
                guild_config.premium.queued_suggestions_prefix
                if await guild_config.premium_is_enabled(ctx)
                else ""
            )
            components = [
                (
                    MessageActionRowBuilder()
                    .add_interactive_button(
                        hikari.ButtonStyle.SUCCESS,
                        "queue_approve|",
                        label=localisations.get_localized_string(
                            "values.suggest.queue_approve", ctx
                        ),
                    )
                    .add_interactive_button(
                        hikari.ButtonStyle.DANGER,
                        "queue_reject|",
                        label=localisations.get_localized_string(
                            "values.suggest.queue_reject", ctx
                        ),
                    )
                )
            ]
            message: hikari.Message = await channel.send(
                content=prefix,
                embed=await qs.as_components(bot),
                components=components,
            )
            qs.channel_id = message.channel_id
            qs.message_id = message.id
            await qs.save()

        logger.debug(
            f"User {ctx.user.id} created new queued"
            f" suggestion in guild {ctx.guild_id}",
            extra={
                "interaction.user.id": ctx.user.id,
                "interaction.guild.id": ctx.guild_id,
            },
        )
        await ctx.respond(
            localisations.get_localized_string(
                "values.suggest.sent_to_queue",
                ctx,
                guild_config=guild_config,
            )
        )
        return None

from __future__ import annotations

import asyncio
import logging
import typing as t

import commons
import hikari
import lightbulb
from lightbulb import di as di_
from lightbulb import localization
from lightbulb.client import (
    GatewayClientAppT,
    DEFAULT_EXECUTION_STEP_ORDER,
    GatewayEnabledClient,
    RestClientAppT,
    RestEnabledClient,
    Client,
)
from lightbulb.commands import execution
from lightbulb.internal import types as lb_types

if t.TYPE_CHECKING:
    from collections.abc import Sequence

    from lightbulb import features as features_

from bot.constants import OTEL_TRACER

LOGGER = logging.getLogger(__name__)


@t.overload
def client_from_app(
    app: GatewayClientAppT,
    default_enabled_guilds: Sequence[hikari.Snowflakeish] = (),
    execution_step_order: Sequence[execution.ExecutionStep] = DEFAULT_EXECUTION_STEP_ORDER,
    default_locale: hikari.Locale = hikari.Locale.EN_US,
    localization_provider: localization.LocalizationProvider = localization.localization_unsupported,
    delete_unknown_commands: bool = True,
    deferred_registration_callback: lb_types.DeferredRegistrationCallback | None = None,
    hooks: Sequence[execution.ExecutionHook] = (),
    sync_commands: bool = True,
    *,
    features: Sequence[features_.Feature] = (),
) -> GatewayEnabledClient: ...
@t.overload
def client_from_app(
    app: RestClientAppT,
    default_enabled_guilds: Sequence[hikari.Snowflakeish] = (),
    execution_step_order: Sequence[execution.ExecutionStep] = DEFAULT_EXECUTION_STEP_ORDER,
    default_locale: hikari.Locale = hikari.Locale.EN_US,
    localization_provider: localization.LocalizationProvider = localization.localization_unsupported,
    delete_unknown_commands: bool = True,
    deferred_registration_callback: lb_types.DeferredRegistrationCallback | None = None,
    hooks: Sequence[execution.ExecutionHook] = (),
    sync_commands: bool = True,
    *,
    features: Sequence[features_.Feature] = (),
) -> RestEnabledClient: ...
def client_from_app(
    app: GatewayClientAppT | RestClientAppT,
    default_enabled_guilds: Sequence[hikari.Snowflakeish] = (),
    execution_step_order: Sequence[execution.ExecutionStep] = DEFAULT_EXECUTION_STEP_ORDER,
    default_locale: hikari.Locale = hikari.Locale.EN_US,
    localization_provider: localization.LocalizationProvider = localization.localization_unsupported,
    delete_unknown_commands: bool = True,
    deferred_registration_callback: lb_types.DeferredRegistrationCallback | None = None,
    hooks: Sequence[execution.ExecutionHook] = (),
    sync_commands: bool = True,
    *,
    features: Sequence[features_.Feature] = (),
) -> Client:
    """
    Create and return the appropriate client implementation from the given application.

    Args:
        app: Application that either supports gateway events, or an interaction server.
        default_enabled_guilds: The guilds that application commands should be created in by default.
        execution_step_order: The order that execution steps will be run in upon command processing.
        default_locale: The default locale to use for command names and descriptions,
            as well as option names and descriptions. Has no effect if localizations are not being used.
            Defaults to :obj:`hikari.locales.Locale.EN_US`.
        localization_provider: The localization provider function to use. This will be called whenever the
            client needs to get the localizations for a key. Defaults to
            :obj:`~lightbulb.localization.localization_unsupported` - the client does not support localizing commands.
            **Must** be passed if you intend to support localizations.
        delete_unknown_commands: Whether to delete existing commands that the client does not have
            an implementation for during command syncing. Defaults to :obj:`True`.
        deferred_registration_callback: The callback to use to resolve which guilds a command should be created in
            if a command is registered using :meth:`~Client.register_deferred`. Allows for commands to be
            dynamically created in guilds, for example enabled on a per-guild basis using feature flags. Defaults
            to :obj:`None`.
        hooks: Execution hooks that should be applied to all commands. These hooks will always run **before**
            all other hooks registered for the same step are executed.
        sync_commands: Whether to sync commands that are registered to the client before starting. Defaults
            to :obj:`True`.
        features: Experimental features to enable for this client.

    Returns:
        :obj:`~Client`: The created client instance.

    .. versionadded:: 3.2.0
        The ``features`` kwarg.
    """
    if execution.ExecutionSteps.INVOKE not in execution_step_order:
        raise ValueError("'execution_step_order' must include ExecutionSteps.INVOKE")

    if isinstance(app, GatewayClientAppT):
        LOGGER.debug("building gateway client from app")
        cls = CustomGatewayLightbulbClient
    else:
        LOGGER.debug("building REST client from app")
        cls = RestEnabledClient

    for experiment in features:
        if not di_.DI_ENABLED and experiment.requires_di_enabled:
            raise ValueError(
                f"cannot enable experiment {experiment.name!r} - DI is required but is disabled"
            )

    return cls(
        app,  # type: ignore[reportArgumentType]
        default_enabled_guilds,
        execution_step_order,
        default_locale,
        localization_provider,
        delete_unknown_commands,
        deferred_registration_callback,
        hooks,
        sync_commands,
        features=features,
    )


class CustomGatewayLightbulbClient(lightbulb.GatewayEnabledClient):
    async def handle_application_command_interaction(
        self, interaction: hikari.CommandInteraction, initial_response_sent: asyncio.Event
    ) -> None:
        out = self._resolve_options_and_command(interaction)
        if out is None:
            return

        options, command = out
        command_locale_key = command._command_data.qualified_name
        try:
            localised_key = self.localization_provider(command_locale_key)[hikari.Locale.EN_GB]
        except Exception as e:
            localised_key = command_locale_key
            LOGGER.error(
                "Failed to find command name for tracing for input %s",
                command_locale_key,
                extra={"traceback": commons.exception_as_string(e)},
            )

        # TODO Test this command name is accurate
        with OTEL_TRACER.start_as_current_span(f"/{localised_key}") as span:
            span.set_attribute("interaction.user.id", interaction.user.id)
            span.set_attribute(
                "interaction.user.global_name",
                (
                    interaction.user.global_name
                    if interaction.user.global_name
                    else interaction.user.username
                ),
            )
            if interaction.guild_id:
                span.set_attribute("interaction.guild.id", interaction.guild_id)

            await super().handle_application_command_interaction(interaction, initial_response_sent)

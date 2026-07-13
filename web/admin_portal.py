from shared.tables import UserConfigs, GuildConfigs, PremiumGuildConfigs
from bot.tables import InternalErrors, MessageAddons, CommandInvokes
from piccolo_admin import create_admin
from piccolo_admin.endpoints import TableConfig
from piccolo_admin.example.tables import AuthenticatorSecret
from piccolo_api.crud.endpoints import OrderBy
from piccolo_api.crud.hooks import HookType, Hook

from web import constants
from web.tables import (
    MagicLinks,
    AuthenticationAttempts,
    OAuthEntry,
    Users,
    Alerts,
    GuildTokens,
)


def post_validate_password_changes(row: Users):
    """Given we dont subclass BaseUser we need to patch this in"""
    try:
        row.split_stored_password(row.password)
    except ValueError:
        row._validate_password(row.password)
        row.password = row.hash_password(row.password)

    return row


def patch_validate_password_changes(row_id: int, values: dict):
    """Given we dont subclass BaseUser we need to patch this in"""
    password: str | None = values.pop("password", None)
    if not password:
        return values

    try:
        Users.split_stored_password(password)
    except ValueError:
        Users._validate_password(password)
        values["password"] = Users.hash_password(password)

    return values


def configure_piccolo_admin():
    alert_tc = TableConfig(Alerts, menu_group="Alerting")
    user_tc = TableConfig(
        Users,
        menu_group="User Management",
        hooks=[
            Hook(hook_type=HookType.pre_save, callable=post_validate_password_changes),
            Hook(hook_type=HookType.pre_patch, callable=patch_validate_password_changes),
        ],
    )
    oauth_entry_tc = TableConfig(OAuthEntry, menu_group="User Management")
    auth_attempt_tc = TableConfig(
        AuthenticationAttempts,
        menu_group="Auditing",
        order_by=[
            OrderBy(AuthenticationAttempts.id, ascending=False),
        ],
    )
    magic_links_tc = TableConfig(
        MagicLinks,
        menu_group="User Management",
        order_by=[
            OrderBy(MagicLinks.id, ascending=False),
        ],
        exclude_visible_columns=[
            MagicLinks.token,
            MagicLinks.cookie,
        ],
    )
    mfa_tc = TableConfig(
        AuthenticatorSecret,
        menu_group="User Management",
        exclude_visible_columns=[
            AuthenticatorSecret.secret,
            AuthenticatorSecret.recovery_codes,
            AuthenticatorSecret.last_used_code,
        ],
        order_by=[
            OrderBy(AuthenticatorSecret.id, ascending=False),
        ],
    )
    guild_tokens_tc = TableConfig(
        GuildTokens,
        menu_group="Stripe",
        order_by=[
            OrderBy(GuildTokens.id, ascending=False),
        ],
    )
    internal_errors_tc = TableConfig(
        InternalErrors,
        menu_group="Bot",
        order_by=[
            OrderBy(InternalErrors.created_at, ascending=False),
        ],
        visible_columns=[
            InternalErrors.id,
            InternalErrors.created_at,
            InternalErrors.error_name,
            InternalErrors.command_name,
            InternalErrors.extra_info,
        ],
    )
    message_addons_tc = TableConfig(
        MessageAddons,
        menu_group="Bot",
        order_by=[
            OrderBy(MessageAddons.id, ascending=False),
        ],
    )
    uc_tc = TableConfig(
        UserConfigs,
        menu_group="Configurations",
        order_by=[
            OrderBy(UserConfigs.id, ascending=False),
        ],
    )
    gc_tc = TableConfig(
        GuildConfigs,
        menu_group="Configurations",
        order_by=[
            OrderBy(GuildConfigs.id, ascending=False),
        ],
    )
    pgc_tc = TableConfig(
        PremiumGuildConfigs,
        menu_group="Configurations",
        order_by=[
            OrderBy(PremiumGuildConfigs.id, ascending=False),
        ],
    )
    invoke_tc = TableConfig(
        CommandInvokes,
        menu_group="Bot",
        order_by=[
            OrderBy(CommandInvokes.id, ascending=False),
        ],
    )

    return create_admin(
        tables=[
            user_tc,
            mfa_tc,
            oauth_entry_tc,
            magic_links_tc,
            alert_tc,
            auth_attempt_tc,
            guild_tokens_tc,
            internal_errors_tc,
            message_addons_tc,
            uc_tc,
            gc_tc,
            invoke_tc,
            pgc_tc,
        ],
        production=constants.IS_PRODUCTION,
        allowed_hosts=constants.SERVING_DOMAIN,
        sidebar_links={"Site root": "/", "API documentation": "/docs/"},
        site_name=constants.SITE_NAME.rstrip() + " Admin",
        auto_include_related=True,
        mfa_providers=[constants.MFA_TOTP_PROVIDER],
        auth_table=Users,  # type: ignore
    )

import logging

from shared.tables import GuildConfigs, PremiumGuildConfigs, UserConfigs

logger = logging.getLogger(__name__)


async def ensure_guild_config(guild_id: int) -> GuildConfigs:
    pgc: PremiumGuildConfigs = await PremiumGuildConfigs.objects().get_or_create(
        PremiumGuildConfigs.guild_id == guild_id
    )
    gc: GuildConfigs = await GuildConfigs.objects().get_or_create(
        (GuildConfigs.guild_id == guild_id) & (GuildConfigs.premium == pgc)
    )
    if gc._was_created:
        logger.debug("Created new GuildConfig for %s", guild_id)

    return gc


async def ensure_user_config(user_id: int) -> UserConfigs:
    uc: UserConfigs = await UserConfigs.objects().get_or_create(
        UserConfigs.user_id == user_id
    )
    if uc._was_created:
        logger.debug("Created new UserConfig for %s", user_id)

    return uc

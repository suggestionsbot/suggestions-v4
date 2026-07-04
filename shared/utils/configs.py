import logging

import hikari

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

    # return gc
    pgc_insert = (
        await PremiumGuildConfigs.insert(
            PremiumGuildConfigs(guild_id=guild_id),
        )
        .on_conflict(action="DO NOTHING", target=(PremiumGuildConfigs.guild_id,))
        .returning(*PremiumGuildConfigs.all_columns())
    )
    if not pgc_insert:
        pgc_insert = (
            await PremiumGuildConfigs.objects()
            .first()
            .where(PremiumGuildConfigs.guild_id == guild_id)
        )
    else:
        # need object for reference reasons
        pgc_insert = PremiumGuildConfigs(**pgc_insert[0])
        pgc_insert._exists_in_db = True

    try_insert = (
        await GuildConfigs.insert(
            GuildConfigs(guild_id=guild_id, premium=pgc_insert),
        )
        .on_conflict(action="DO NOTHING", target=(GuildConfigs.guild_id,))
        .returning(*GuildConfigs.all_columns())
    )
    if try_insert:
        # New object
        logger.debug("Created new GuildConfigs for %s", guild_id)
        obj = GuildConfigs(**try_insert[0])
        obj._exists_in_db = True
        return obj

    return await GuildConfigs.objects().first().where(GuildConfigs.guild_id == guild_id)


async def ensure_user_config(
    user_id: int, *, locale: hikari.Locale | str = hikari.Locale.EN_GB
) -> UserConfigs:
    try_insert = (
        await UserConfigs.insert(
            UserConfigs(user_id=user_id, primary_language_raw=locale),
        )
        .on_conflict(action="DO NOTHING", target=(UserConfigs.user_id,))
        .returning(*UserConfigs.all_columns())
    )
    if try_insert:
        # New object
        logger.debug("Created new UserConfig for %s", user_id)
        obj = UserConfigs(**try_insert[0])
        obj._exists_in_db = True
        return obj

    return await UserConfigs.objects().first().where(UserConfigs.user_id == user_id)

from datetime import timedelta

import hikari
import httpx

from shared.tables import UserConfigs


async def fetch_user_avatar(user_id: int, *, rest) -> hikari.URL | None:
    """Fetches the user avatar, returning None if the avatar is not available."""
    from web.constants import REDIS_CLIENT

    cache_key = f"avatars/{user_id}"
    data = await REDIS_CLIENT.get(cache_key)
    if data is not None:
        assert isinstance(data, bytes), "Redis returned a string"
        # Empty means Discord told us there is no avatar
        return hikari.URL(data.decode("utf-8")) if data else None

    async with httpx.AsyncClient() as client:
        try:
            user: hikari.User = await rest.fetch_user(user_id)
        except hikari.NotFoundError:
            await REDIS_CLIENT.set(cache_key, b"", ex=timedelta(hours=12))
            return None

        url = user.display_avatar_url.url

        try:
            resp = await client.get(url)
        except httpx.ReadTimeout:
            return None

        if resp.status_code == 404:  # noqa: PLR2004
            await REDIS_CLIENT.set(cache_key, b"", ex=timedelta(hours=12))
            return None

        if resp.status_code != 200:  # noqa: PLR2004
            return None

        await REDIS_CLIENT.set(
            cache_key,
            url.encode("utf-8"),
            ex=timedelta(hours=12),
        )

    return hikari.URL(url)


async def fetch_user_dm_channel_id(
    user_config: UserConfigs, *, rest: hikari.api.RESTClient
) -> hikari.Snowflakeish:
    if user_config.dm_channel_id is not None:
        return user_config.dm_channel_id

    dm_channel = await rest.create_dm_channel(user_config.user_id)
    user_config.dm_channel_id = dm_channel.id
    await user_config.save()
    return dm_channel.id

from datetime import timedelta

import hikari
import httpx


async def fetch_user_avatar(user_id: int, *, rest) -> hikari.URL | None:
    """Fetches the user avatar, returning None if the avatar is not available."""
    from web.constants import REDIS_CLIENT

    data = await REDIS_CLIENT.get(f"avatars/{user_id}")
    if data is not None:
        assert isinstance(data, bytes), "Redis returned a string"
        return hikari.URL(data.decode("utf-8"))

    async with httpx.AsyncClient() as client:
        user: hikari.User = await rest.fetch_user(user_id)
        url = user.display_avatar_url.url

        try:
            resp = await client.get(url)
        except httpx.ReadTimeout:
            return None

        if resp.status_code != 200:  # noqa: PLR2004
            return None

        await REDIS_CLIENT.set(
            f"avatars/{user_id}",
            url.encode("utf-8"),
            ex=timedelta(hours=12),
        )

    return hikari.URL(url)

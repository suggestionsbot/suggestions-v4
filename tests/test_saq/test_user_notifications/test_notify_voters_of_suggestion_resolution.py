import bot.constants
import datetime

from shared.saq.user_notifications import (
    notify_voters_of_suggestion_resolution,
    get_voters_for_suggestion_with_notifications_enabled,
)
from shared.tables import (
    PremiumUserConfigs,
    SuggestionVotes,
    Suggestions,
    SuggestionStateEnum,
    GuildConfigs,
    UserConfigs,
    SuggestionsVoteTypeEnum,
)
from shared.utils import configs
from web.tables import UserTokens
from web.util.table_mixins import utc_now

USER_ID = 12345
GUILD_ID = 23456
DISPLAY_NAME = "Skelmis"
SID = "aaaa1111"


async def create_suggestion(
    *,
    sid: str = SID,
    guild_id: int = GUILD_ID,
    user_id: int = USER_ID,
    state: SuggestionStateEnum = SuggestionStateEnum.PENDING,
) -> tuple[Suggestions, GuildConfigs, UserConfigs]:
    """Persists a suggestion which can then be voted upon."""
    guild_config = await configs.ensure_guild_config(guild_id)
    user_config = await configs.ensure_user_config(user_id)

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


async def grant_user_premium(*, expired: bool = False) -> None:
    """Gives the guild an active premium token, as redeeming one would."""
    offset = datetime.timedelta(days=-1 if expired else 30)
    await UserTokens(
        subscription_id="sub_test",
        subscription_item_id="si_test",
        user_id=USER_ID,
        expires_at=utc_now() + offset,
    ).save()


async def test_fetches_users_for_notifications(monkeypatch) -> None:
    monkeypatch.setattr(bot.constants, "ENABLE_FREE_USER_PREMIUM", False)
    suggestion, gc, uc = await create_suggestion()
    r_1 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_1 == []

    # First vote, no premium
    vote_1 = SuggestionVotes(
        suggestion=suggestion, vote_type=SuggestionsVoteTypeEnum.UpVote, user_id=USER_ID
    )
    await vote_1.save()
    r_2 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_2 == []

    # Second vote, premium config but no notif
    await uc.fetch_premium_object()
    r_2 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_2 == []

    # Third vote, premium config with notif but no premium
    puc = await uc.fetch_premium_object()
    puc.wants_voting_notifications = True
    await puc.save()
    r_3 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_3 == []

    # Fourth vote, premium config with expired premium and notif
    await grant_user_premium(expired=True)
    r_4 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_4 == []

    # Fifth vote, premium config with premium and notif
    await grant_user_premium()
    r_5 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_5 == [vote_1]


async def test_enable_user_premium(monkeypatch) -> None:
    monkeypatch.setattr(bot.constants, "ENABLE_FREE_USER_PREMIUM", True)
    suggestion, gc, uc = await create_suggestion()
    r_1 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_1 == []

    # First vote, no premium
    vote_1 = SuggestionVotes(
        suggestion=suggestion, vote_type=SuggestionsVoteTypeEnum.UpVote, user_id=USER_ID
    )
    await vote_1.save()
    r_2 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_2 == []

    # Second vote, premium config but no notif
    await uc.fetch_premium_object()
    r_2 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_2 == []

    # Third vote, premium config with notif
    puc = await uc.fetch_premium_object()
    puc.wants_voting_notifications = True
    await puc.save()
    r_3 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_3 == [vote_1]

    # Fourth vote, premium config with expired premium and notif
    await grant_user_premium(expired=True)
    r_4 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_4 == [vote_1]

    # Fifth vote, premium config with premium and notif
    await grant_user_premium()
    r_5 = await get_voters_for_suggestion_with_notifications_enabled(suggestion)
    assert r_5 == [vote_1]

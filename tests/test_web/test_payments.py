import logging
from tests.conftest import BaseGiven, GuildTokenT
from web.util import payments

Given = BaseGiven()


async def test_existing_subscription(caplog) -> None:
    user = Given.user("test@suggestions.gg").object
    Given.x_guild_tokens_exist(GuildTokenT(subscription_id="test", user=user))

    with caplog.at_level(logging.DEBUG):
        await payments.fulfil_guild_purchase("test", user=user)

    assert caplog.messages == [
        "Got asked to fulfil guild purchase for 'test' but was already handled"
    ]

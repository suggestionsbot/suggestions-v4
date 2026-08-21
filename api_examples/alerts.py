from typing import Self
import asyncio
import datetime
from enum import Enum
from uuid import UUID

import httpx
from pydantic import Field, BaseModel

from api_examples.client import CRUDClient, SearchModel, JoinModel, SearchItemIn
from api_examples.authentication import APIAuth


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class AlertLevels(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"

    @classmethod
    def from_str(cls, level: str) -> Self:
        return cls[level.upper()]


class NewAlertModel(BaseModel):
    target: int = Field(description="The ID of the user to show the alert to")
    message: str = Field(description="The message to display")
    level: AlertLevels = Field(description="The level of the alert when displayed")


class UserModel(BaseModel):
    username: str = Field(description="The username of the user")
    email: str = Field(description="The email of the user")


class AlertOutModel(NewAlertModel):
    target: UserModel = Field(description="The user who will receive this alert")
    uuid: UUID = Field(description="The UUID primary key of this alert")
    has_been_shown: bool = Field(description="Has the user seen this yet?")
    was_shown_at: datetime.datetime | None = Field(
        description="The time the user was shown the alert"
    )


class AlertPatchModel(BaseModel):
    has_been_shown: bool | None = Field(
        default=None,
        description="Has the user seen this yet?",
    )
    was_shown_at: datetime.datetime | None = Field(
        default=None, description="The time the user was shown the alert"
    )


# noinspection PyTypeChecker
async def main():
    website_session = "fhuu1ytDrFpird4SfTQajhE5wwtSGiWfXyI9V6CiDtk"
    base_url = "http://127.0.0.1:2300"
    async with httpx.AsyncClient(base_url=base_url) as client:
        api_auth = APIAuth(client=client)
        await api_auth.create_initial_token(website_session)
        user = await api_auth.fetch_me()

    client: CRUDClient[NewAlertModel, AlertPatchModel, AlertOutModel] = CRUDClient(
        f"{base_url}/api/alerts",
        AlertOutModel,
        headers={"X-API-KEY": api_auth.token},
    )

    # The CRUDClient even smoothly handles 429's!
    for _ in range(8):  # Ratelimit is 5/sec
        await client.get_all_records_as_list()

    # Create an alert, mark it as seen and then delete it
    alert = await client.create_record(
        NewAlertModel(target=user.user_id, message="Hello World!", level=AlertLevels.INFO)
    )
    await client.patch_record(
        alert.uuid, AlertPatchModel(has_been_shown=True, was_shown_at=utc_now())
    )
    await client.delete_record(alert.uuid)

    # Create some alerts, iterate over them and refetch some
    await client.create_record(
        NewAlertModel(target=user.user_id, message="Hello World!", level=AlertLevels.INFO)
    )
    alert_1 = await client.create_record(
        NewAlertModel(target=user.user_id, message="Oh no", level=AlertLevels.WARNING)
    )
    await client.patch_record(
        alert_1.uuid, AlertPatchModel(was_shown_at=utc_now(), has_been_shown=True)
    )
    # Oops, undo that
    await client.patch_record(
        alert_1.uuid, AlertPatchModel(has_been_shown=False, was_shown_at=None)
    )
    alert_2 = await client.create_record(
        NewAlertModel(target=user.user_id, message="Not good!", level=AlertLevels.ERROR)
    )
    await client.patch_record(
        alert_2.uuid, AlertPatchModel(was_shown_at=utc_now(), has_been_shown=True)
    )
    total_records = await client.get_total_record_count()
    print(f"We currently have {total_records.total_records} alerts!")

    have_been_seen = 0
    async for group in client.get_all_records():
        for row in group:
            if row.has_been_shown:
                have_been_seen += 1

            await client.delete_record(row.uuid)

    print(
        f"Only {have_been_seen} alerts have been shown though!"
        f"\n\tP.s. I deleted all alerts mwaha!"
    )

    # --- No alerts exist at this stage ---
    alert_1 = await client.create_record(
        NewAlertModel(target=user.user_id, message="Not good!", level=AlertLevels.WARNING)
    )
    await client.patch_record(
        alert_1.uuid, AlertPatchModel(was_shown_at=utc_now(), has_been_shown=True)
    )
    await client.create_record(
        NewAlertModel(target=user.user_id, message="Its fine", level=AlertLevels.ERROR)
    )
    await client.create_record(
        NewAlertModel(target=user.user_id, message="Hello World", level=AlertLevels.INFO)
    )
    await client.create_record(
        NewAlertModel(target=2, message="Nice!", level=AlertLevels.SUCCESS)
    )

    available_filters = await client.get_search_filters()
    print("Search options", available_filters.filters)

    r_1 = await client.search_records_as_list(
        SearchModel(
            filters=[
                SearchItemIn(
                    column_name="target",
                    operation="equals",
                    search_value="1",
                ),
            ]
        )
    )
    print(f"Found {len(r_1)} alerts where the target had the id 1!")
    r_2 = await client.search_records_as_list(
        SearchModel(
            filters=[
                SearchItemIn(
                    column_name="message",
                    operation="starts_with",
                    search_value="Hello",
                ),
                SearchItemIn(
                    column_name="target",
                    operation="equals",
                    search_value="1",
                ),
            ]
        )
    )
    print(
        f"Found {len(r_2)} alerts where the message starts with 'Hello' and is targeting user 1"
    )
    r_3 = await client.search_records_as_list(
        SearchModel(
            filters=[
                JoinModel(
                    operand="or",
                    filters=[
                        SearchItemIn(
                            column_name="level",
                            operation="equals",
                            search_value="success",
                        ),
                        SearchItemIn(
                            column_name="target",
                            operation="equals",
                            search_value="1",
                        ),
                    ],
                ),
            ]
        )
    )
    print(f"Found {len(r_3)} alerts with complex query")

    r_4 = await client.search_records_as_list(
        SearchModel(
            filters=[
                SearchItemIn(
                    column_name="has_been_shown",
                    operation="equals",
                    search_value="1",
                ),
            ]
        )
    )
    print(f"Found {len(r_4)} alerts have been shown")

    # Cleanup once done
    async for group in client.get_all_records():
        for row in group:
            await client.delete_record(row.uuid)


if __name__ == "__main__":
    asyncio.run(main())

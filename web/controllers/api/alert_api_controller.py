import datetime
from typing import Annotated, Any
from uuid import UUID

from litestar import patch, Request, post, get, delete
from litestar.datastructures import State
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.params import Parameter
from pydantic import BaseModel, Field

from web.crud.controller import (
    CRUDController,
    GetAllResponseModel,
    CRUDMeta,
    GetCountResponseModel,
    CRUD_BASE_OPENAPI_RESPONSES,
    get_user_ratelimit_key,
    SearchableColumn,
    SearchTableModel,
    SearchRequestModel,
    SearchModel,
    QueryT,
)
from web.guards import ensure_api_token
from web.middleware import UserFromAPIKey
from web.tables import Alerts, AlertLevels, Users, APIToken


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
    has_been_shown: bool = Field(
        default=None, description="Has the user seen this yet?"
    )
    was_shown_at: datetime.datetime | None = Field(
        default=None, description="The time the user was shown the alert"
    )


crud_meta = CRUDMeta(
    BASE_CLASS=Alerts,
    BASE_CLASS_PK=Alerts.uuid,
    BASE_CLASS_CURSOR_COL=Alerts.id,
    BASE_CLASS_ORDER_BY=Alerts.id,
    DTO_OUT=AlertOutModel,
    PREFETCH_COLUMNS=[Alerts.target],
    AVAILABLE_FILTERS=[
        SearchableColumn(
            columns=[
                SearchTableModel(
                    column=Alerts.target, column_name="target", expected_value_type=int
                ),
                SearchTableModel(
                    column=Alerts.level, column_name="level", expected_value_type=str
                ),
                SearchTableModel(
                    column=Alerts.has_been_shown,
                    column_name="has_been_shown",
                    expected_value_type=bool,
                ),
            ],
            supports_equals=True,
        ),
        SearchableColumn(
            columns=[
                SearchTableModel(
                    column=Alerts.message,
                    column_name="message",
                    expected_value_type=str,
                ),
            ],
            supports_equals=True,
            supports_contains=True,
            supports_starts_with=True,
            supports_ends_with=True,
        ),
    ],
)


rate_limit_config = RateLimitConfig(
    rate_limit=("second", 5),  # noqa
    identifier_for_request=get_user_ratelimit_key,
)


class APIAlertController[AlertOutModel](CRUDController):
    path = "/api/alerts"
    tags = ["Alerts"]
    META = crud_meta
    middleware = [UserFromAPIKey, rate_limit_config.middleware]
    security = [{"apiKey": []}]

    async def add_custom_where(
        self, request: Request[Users, APIToken, State], query: QueryT
    ) -> QueryT:
        if request.user.admin or request.user.superuser:
            # Admins can access any object they want
            return query

        # noinspection PyTypeChecker
        return query.where(Alerts.target == request.user)

    @get(
        "/",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
    )
    async def get_all_records(
        self,
        request: Request[Users, APIToken, State],
        page_size: int = Parameter(
            query="_page_size",
            default=500,
            required=False,
            le=500,
            ge=1,
        ),
        next_cursor: str | None = Parameter(query="_next_cursor", required=False),
    ) -> GetAllResponseModel[AlertOutModel]:
        return await super().get_all_records(
            request, page_size=page_size, next_cursor=next_cursor
        )

    @get(
        "/{primary_key:uuid}",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
    )
    async def get_object(
        self,
        request: Request,
        primary_key: Annotated[
            UUID,
            Parameter(
                title="Object ID",
                description="The ID of the object you wish to retrieve",
            ),
        ],
    ) -> AlertOutModel:
        return await super().get_object(request, primary_key)

    @delete(
        "/{primary_key:str}",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
    )
    async def delete_object(
        self,
        request: Request,
        primary_key: Annotated[
            Any,
            Parameter(
                title="Object ID",
                description="The ID of the object you wish to delete",
            ),
        ],
    ) -> None:
        return await super().delete_object(request, primary_key)

    @get(
        "/meta/count",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
    )
    async def get_record_count(self, request: Request) -> GetCountResponseModel:
        return await super().get_record_count(request)

    @post(
        "/",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
        status_code=201,
    )
    async def create_object(
        self, request: Request[Users, APIToken, State], data: NewAlertModel
    ) -> AlertOutModel:
        if not (request.user.admin or request.user.superuser):
            # Only admins can target other users with alerts
            data.target = request.user.id

        return await super().create_object(request, data)

    @patch(
        "/{primary_key:str}",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
    )
    async def patch_object(
        self,
        request: Request,
        primary_key: Annotated[
            Any,
            Parameter(
                title="Object ID",
                description="The ID of the object you wish to delete",
            ),
        ],
        data: AlertPatchModel,
    ) -> AlertOutModel:
        return await super().patch_object(
            request,
            primary_key,
            data.model_dump(exclude_unset=True),
            # data.model_dump(exclude_unset=True, exclude_none=True),
        )

    @get("/meta/search/filters")
    async def get_available_search_filters(
        self, request: Request
    ) -> SearchRequestModel:
        return await super().get_available_search_filters(request)

    @post("/search", responses=CRUD_BASE_OPENAPI_RESPONSES, status_code=200)
    async def run_search(
        self,
        request: Request,
        data: SearchModel,
        page_size: int = Parameter(
            query="_page_size",
            default=500,
            required=False,
            le=500,
            ge=1,
        ),
        next_cursor: str | None = Parameter(query="_next_cursor", required=False),
    ) -> GetAllResponseModel[AlertOutModel]:
        return await super().search(request, data, page_size, next_cursor)

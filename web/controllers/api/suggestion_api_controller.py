from datetime import datetime
from typing import Any

from piccolo.columns import Or
from pydantic import BaseModel, Field, model_validator
from litestar.params import Parameter

from shared.tables import Suggestions, SuggestionVotes, SuggestionsVoteTypeEnum
from litestar import Request, get, post
from litestar.datastructures import State
from litestar.middleware.rate_limit import RateLimitConfig

from web.controllers.oauth_controller import DISCORD_OAUTH
from web.crud.controller import (
    CRUDController,
    get_user_ratelimit_key,
    QueryT,
    CRUD_BASE_OPENAPI_RESPONSES,
    GetAllResponseModel,
    CRUDMeta,
    SearchableColumn,
    SearchTableModel,
    SearchRequestModel,
    SearchModel,
)
from web.middleware import UserFromAPIKey
from web.tables import Users, APIToken


class SuggestionOutModel(BaseModel):
    sID: str = Field(description="The user facing id. This should be used everywhere.")
    suggestion: str = Field(description="Suggestion content")
    guild_id: int = Field(description="The guild this suggestion is in")
    user_id: int | None = Field(
        description="The author of this suggestion. This is empty if the author is anonymous",
        default=None,
    )
    up_votes: int | None = Field(
        default=None,
        description="The total up votes on this suggestion. Not present by default.",
    )
    down_votes: int | None = Field(
        default=None,
        description="The total down votes on this suggestion. Not present by default.",
    )
    state: str = Field(description="The current state of the suggestion")
    moderator_note: str | None = Field(
        description="An optional note that was added by a moderator", default=None
    )
    moderator_note_added_by: int | None = Field(
        description="The moderator who added the note to this suggestion. "
        "This is empty if the author is anonymous",
        default=None,
    )
    channel_id: int | None = Field(
        description="If this suggestion has been sent to discord, what channel is it in?",
        default=None,
    )
    message_id: int | None = Field(
        description="If this suggestion has been sent to discord, what is it's message id?",
        default=None,
    )
    thread_id: int | None = Field(
        description="If a thread was automatically created for this suggestion, what was it?",
        default=None,
    )
    resolved_by: int | None = Field(
        description="If the state is approved or rejected, who made that call? "
        "This is empty if the resolver is anonymous",
        default=None,
    )
    resolved_note: str | None = Field(
        description="If the state is approved or rejected, did they add a "
        "message to the closing state?",
        default=None,
    )
    resolved_at: datetime | None = Field(
        description="When was this suggestion resolved?", default=None
    )
    created_at: datetime = Field(
        description="When was this suggestion created?",
    )
    image_urls: list[str] = Field(
        description="Optional image URLs to include in the suggestion embed. "
        "Will usually be a bot managed Cloudflare R2 link.",
    )

    @model_validator(mode="before")
    @classmethod
    def set_state(cls, data: dict) -> dict:
        if isinstance(data, dict):
            data["state"] = data["state_raw"]

        return data

    @model_validator(mode="before")
    @classmethod
    def set_guild_id(cls, data: dict) -> dict:
        if isinstance(data, dict):
            data["guild_id"] = data["guild_configuration"]["guild_id"]

        return data

    @model_validator(mode="before")
    @classmethod
    def set_user_id(cls, data: dict) -> dict:
        if isinstance(data, dict) and data["author_display_name"] != "Anonymous":
            data["user_id"] = data["user_configuration"]["user_id"]

        return data

    @model_validator(mode="before")
    @classmethod
    def set_resolved_by(cls, data: dict) -> dict:
        if isinstance(data, dict) and data["resolved_by_display_text"] == "Anonymous":
            data["resolved_by"] = None

        return data

    @model_validator(mode="before")
    @classmethod
    def set_moderator_note_author(cls, data: dict) -> dict:
        if (
            isinstance(data, dict)
            and data["moderator_note_added_by_display_text"] == "Anonymous"
        ):
            data["moderator_note_added_by"] = None

        return data


crud_meta = CRUDMeta(
    BASE_CLASS=Suggestions,
    BASE_CLASS_PK=Suggestions.sID,
    BASE_CLASS_CURSOR_COL=Suggestions.id,
    BASE_CLASS_ORDER_BY=Suggestions.id,
    DTO_OUT=SuggestionOutModel,
    PREFETCH_COLUMNS=[Suggestions.user_configuration, Suggestions.guild_configuration],
    AVAILABLE_FILTERS=[
        SearchableColumn(
            columns=[
                SearchTableModel(
                    column=Suggestions.guild_configuration.guild_id,
                    column_name="guild_id",
                    expected_value_type=int,
                ),
                SearchTableModel(
                    column=Suggestions.sID,
                    column_name="sID",
                    expected_value_type=str,
                ),
            ],
            supports_equals=True,
        ),
        SearchableColumn(
            columns=[
                SearchTableModel(
                    column=Suggestions.suggestion,
                    column_name="suggestion",
                    expected_value_type=str,
                ),
            ],
            supports_equals=True,
            supports_contains=True,
            supports_starts_with=True,
            supports_ends_with=True,
        ),
        SearchableColumn(
            columns=[
                SearchTableModel(
                    column=Suggestions.state_raw,
                    column_name="state",
                    expected_value_type=str,
                ),
            ],
            supports_equals=True,
        ),
        SearchableColumn(
            columns=[
                SearchTableModel(
                    column=Suggestions.created_at,
                    column_name="created_at",
                    expected_value_type=datetime,
                ),
            ],
            supports_equals=True,
            supports_greater_than=True,
            supports_greater_than_equal=True,
            supports_less_than=True,
            supports_less_than_equal=True,
        ),
    ],
)


rate_limit_config = RateLimitConfig(
    rate_limit=("second", 5),
    identifier_for_request=get_user_ratelimit_key,
)


class APISuggestionController(CRUDController):
    path = "/api/suggestions"
    tags = ["Suggestions"]  # noqa: RUF012
    META = crud_meta
    middleware = [UserFromAPIKey, rate_limit_config.middleware]  # noqa: RUF012
    security = [{"apiKey": []}]  # noqa: RUF012

    async def add_custom_where(
        self, request: Request[Users, APIToken, State], query: QueryT
    ) -> QueryT:
        if request.user.admin or request.user.superuser:
            # Admins can access any object they want
            return query

        # TODO Cache this lookup
        oauth_user = await request.user.get_oauth_entry()
        assert oauth_user is not None
        guilds = await DISCORD_OAUTH.get_user_guilds(
            oauth_user.access_token, user_id=oauth_user.oauth_id
        )
        guild_ids = [int(k["id"]) for k in guilds]
        return query.where(
            Or(
                Suggestions.user_configuration.user_id == oauth_user.oauth_id,
                Suggestions.guild_configuration.guild_id.is_in(guild_ids),
            )
        )

    @get(
        "/meta/search/filters",
        name="Get Search Filters",
        description="Fetch the various supported filter configurations.",
    )
    async def get_available_search_filters(self, request: Request) -> SearchRequestModel:
        return await super().get_available_search_filters(request)

    @get(
        "/",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
        name="Get Suggestions",
        description="Fetch all suggestions as per filter parameters.",
    )
    async def get_suggestions(
        self,
        request: Request[Users, APIToken, State],
        page_size: int = Parameter(
            query="_page_size",
            default=500,
            required=False,
            le=500,
            ge=1,
        ),
        next_cursor: str | None = Parameter(
            query="_next_cursor", required=False, default=None
        ),
        with_vote_counts: bool = Parameter(
            query="with_vote_counts",
            required=False,
            default=False,
            description="Include vote totals in suggestion responses",
        ),
        my_suggestions: bool = Parameter(
            query="my_suggestions",
            required=False,
            default=False,
            description="Only fetch suggestions created by the user",
        ),
    ) -> GetAllResponseModel[SuggestionOutModel]:
        base_query = await self.build_base_query(
            request, page_size=page_size, next_cursor=next_cursor
        )

        if my_suggestions:
            oauth_user = await request.user.get_oauth_entry()
            assert oauth_user is not None
            base_query = base_query.where(
                Suggestions.user_configuration.user_id == oauth_user.oauth_id
            )

        rows: list[Suggestions] = await base_query.run()
        next_cursor = None
        if len(rows) > page_size:
            final_row = rows.pop(-1)
            # noinspection PyProtectedMember
            next_cursor = getattr(
                final_row,
                self.META.BASE_CLASS_CURSOR_COL._meta.name,
            )

        data = await self.enrich_results(rows, with_vote_counts)
        return GetAllResponseModel(
            data=data,
            next_cursor=self._encode_cursor(next_cursor),
        )

    @post(
        "/search",
        responses=CRUD_BASE_OPENAPI_RESPONSES,
        status_code=200,
        exclude_from_csrf=True,
        name="Search Suggestions",
        description="Fetch all suggestions as per filter parameters.",
    )
    async def run_suggestions_search(
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
        with_vote_counts: bool = Parameter(
            query="with_vote_counts", required=False, default=False
        ),
    ) -> GetAllResponseModel[SuggestionOutModel]:
        base_query = await self.build_base_query(
            request, page_size=page_size, next_cursor=next_cursor
        )
        await self._apply_filters_to_query(base_query, data)

        rows: list[Suggestions] = await base_query.run()
        next_cursor = None
        if len(rows) > page_size:
            final_row = rows.pop(-1)
            # noinspection PyProtectedMember
            next_cursor = getattr(
                final_row,
                self.META.BASE_CLASS_CURSOR_COL._meta.name,  # type: ignore
            )

        data: list[SuggestionOutModel] = await self.enrich_results(rows, with_vote_counts)
        return GetAllResponseModel(
            data=data,
            next_cursor=self._encode_cursor(next_cursor),
        )

    async def enrich_results(
        self, rows: list, with_vote_counts: bool
    ) -> list[SuggestionOutModel]:
        vote_lookup: dict[int, tuple[int, int]] = {}
        if with_vote_counts:
            for row in rows:
                up_votes = (
                    await SuggestionVotes.count()
                    .where(SuggestionVotes.suggestion == row.id)
                    .where(SuggestionVotes.vote_type == SuggestionsVoteTypeEnum.UpVote)
                )
                down_votes = (
                    await SuggestionVotes.count()
                    .where(SuggestionVotes.suggestion == row.id)
                    .where(SuggestionVotes.vote_type == SuggestionsVoteTypeEnum.DownVote)
                )
                vote_lookup[row["id"]] = (up_votes, down_votes)
        data = []
        for row in rows:
            out: SuggestionOutModel = self._transform_row_to_output(row)
            if with_vote_counts:
                out.up_votes = vote_lookup[row.id][0]
                out.down_votes = vote_lookup[row.id][1]
            data.append(out)

        return data

from piccolo.columns import Or
from pydantic import BaseModel, Field, model_validator
from litestar.params import Parameter

from shared.tables import Suggestions, SuggestionVotes, SuggestionsVoteTypeEnum
from litestar import Request, get
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
)
from web.middleware import UserFromAPIKey
from web.tables import Users, APIToken


class SuggestionOutModel(BaseModel):
    suggestion: str = Field(description="Suggestion content")
    guild_id: int = Field(description="The guild this suggestion is in")
    user_id: int | None = Field(
        description="The author of this suggestion. This is empty if the author is anonymous"
    )
    up_votes: int | None = Field(
        default=None,
        description="The total up votes on this suggestion. Not present by default.",
    )
    down_votes: int | None = Field(
        default=None,
        description="The total down votes on this suggestion. Not present by default.",
    )

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
                    column=Suggestions.user_configuration.user_id,
                    column_name="user_id",
                    expected_value_type=int,
                ),
                SearchTableModel(
                    column=Suggestions.guild_configuration.guild_id,
                    column_name="guild_id",
                    expected_value_type=int,
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

    @get("/meta/search/filters")
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
            default=250,
            required=False,
            le=250,
            ge=1,
        ),
        next_cursor: str | None = Parameter(
            query="_next_cursor", required=False, default=None
        ),
        user_id: int | None = Parameter(query="user_id", required=False, default=None),
        guild_id: int | None = Parameter(query="guild_id", required=False, default=None),
        with_vote_counts: bool = Parameter(
            query="with_vote_counts", required=False, default=False
        ),
    ) -> GetAllResponseModel[SuggestionOutModel]:
        base_query = await self.build_base_query(
            request, page_size=page_size, next_cursor=next_cursor
        )

        if guild_id is not None:
            base_query = base_query.where(
                Suggestions.guild_configuration.guild_id == guild_id
            )

        if user_id is not None:
            base_query = base_query.where(
                Suggestions.user_configuration.user_id == user_id
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

        return GetAllResponseModel(
            data=data,
            next_cursor=self._encode_cursor(next_cursor),
        )

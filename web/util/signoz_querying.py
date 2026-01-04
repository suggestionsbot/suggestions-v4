import asyncio
from datetime import timedelta
from typing import Final

import arrow
import httpx

from web import constants

BASE_URL: Final[str] = constants.SIGNOZ_API_URL
HEADERS = {"SIGNOZ-API-KEY": constants.SIGNOZ_API_KEY}

UNIQUE_GLOBAL_USERS_QUERY = [
    {
        "type": "builder_query",
        "spec": {
            "name": "A",
            "signal": "traces",
            "aggregations": [{"expression": "count_distinct(interaction.author.id)"}],
            "filter": {
                "expression": 'service.name = "suggestions-bot-v3" and deployment.environment = "Production"'
            },
        },
    }
]
UNIQUE_GLOBAL_GUILDS_QUERY = [
    {
        "type": "builder_query",
        "spec": {
            "name": "A",
            "signal": "traces",
            "aggregations": [{"expression": "count_distinct(interaction.guild.id)"}],
            "filter": {
                "expression": 'service.name = "suggestions-bot-v3" and deployment.environment = "Production"'
            },
        },
    }
]


def build_trace_query(query, timespan: timedelta) -> dict:
    return {
        "start": int(
            arrow.utcnow().shift(seconds=timespan.total_seconds()).float_timestamp
            * 1000
        ),
        "end": int(arrow.utcnow().float_timestamp * 1000),
        "requestType": "scalar",
        "compositeQuery": {"queries": query},
    }


async def main():
    all_dashboards: httpx.Response = httpx.get(
        f"{BASE_URL}/v1/dashboards/019b63ab-7da9-71aa-844f-12cdb06625f1",
        headers=HEADERS,
    )
    data = all_dashboards.json()["data"]["data"]
    print("Dashboard entries", data)

    widgets = data["widgets"]
    print(f"Attempting for users")
    query_result: httpx.Response = httpx.post(
        f"{BASE_URL}/v5/query_range",
        headers=HEADERS,
        json=build_trace_query(UNIQUE_GLOBAL_USERS_QUERY, timedelta(days=-1)),
    )
    print(
        "Users in last day",
        query_result.json()["data"]["data"]["results"][0]["data"][0][0],
    )


if __name__ == "__main__":
    asyncio.run(main())

from litestar import Request


async def retrieve_api_key(request: Request) -> str:
    key = request.headers.get("X-API-KEY", None)
    if key is None:
        raise ValueError("Expected X-API-KEY, found None")

    return key

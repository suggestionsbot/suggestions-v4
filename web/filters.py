from collections.abc import Mapping
import datetime
from typing import Any

from humanize import precisedelta
from litestar.exceptions import ImproperlyConfiguredException
from litestar.plugins.flash import get_flashes as _get_flashes


def format_datetime(
    value: datetime.datetime | datetime.date | datetime.time, fmt="medium"
):
    if fmt == "full":
        fmt = "%I:%M%p, %a %d %b %Y"
    elif fmt == "medium":
        fmt = "%I:%M%p, %d/%m/%Y"
    elif fmt == "date":
        fmt = "%d/%m/%Y"
    elif fmt == "time":
        fmt = "%I:%M%p"

    return value.strftime(fmt)


def precise_delta(timedelta: datetime.timedelta):
    return precisedelta(timedelta)


def safe_get_flashes(context: Mapping[str, Any]) -> Any:  # noqa: ANN401
    try:
        return _get_flashes(context)
    except ImproperlyConfiguredException:
        return []

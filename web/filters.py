import datetime

from humanize import precisedelta


def format_datetime(value: datetime.datetime | datetime.date | datetime.time, fmt="medium"):
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

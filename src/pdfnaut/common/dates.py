from __future__ import annotations

import datetime
import re


def parse_iso8824(date_string: str) -> datetime.datetime:
    """Parses an ISO/IEC 8824 date string into a :class:`datetime.datetime` object
    (for example, ``D:20010727133720``).

    This is the type of date string described in § 7.9.4 Dates of the PDF spec.
    """

    # dates may end with an apostrophe (pdf 1.7 and below)
    if date_string.endswith("'"):
        date_string = date_string[:-1]

    pattern = re.compile(
        r"""^D:(?P<year>\d{4})(?P<month>\d{2})?(?P<day>\d{2})?                       # date
                (?P<hour>\d{2})?(?P<minute>\d{2})?(?P<second>\d{2})?                 # time
                (?P<offset>[-+Z])?(?P<offset_hour>\d{2})?(?P<offset_minute>'\d{2})?$ # offset
        """,
        re.X,
    )

    mat = pattern.match(date_string)
    if not mat:
        raise ValueError(f"Invalid date format: {date_string!r}")

    offset_sign = mat.group("offset")
    if offset_sign is None or offset_sign == "Z":
        offset_hour = 0
        offset_minute = 0
    else:
        offset_hour = int(mat.group("offset_hour") or 0)
        offset_minute = int((mat.group("offset_minute") or "'0")[1:])

    if offset_sign == "-":
        offset_hour = -offset_hour

    delta = datetime.timedelta(hours=offset_hour, minutes=offset_minute)

    return datetime.datetime(
        year=int(mat.group("year")),
        month=int(mat.group("month") or 1),
        day=int(mat.group("day") or 1),
        hour=int(mat.group("hour") or 0),
        minute=int(mat.group("minute") or 0),
        second=int(mat.group("second") or 0),
        tzinfo=datetime.timezone(delta),
    )


def encode_iso8824(date: datetime.datetime) -> str:
    """Encodes a :class:`datetime.datetime` object into an ISO 8824 date string suitable
    for storage in a PDF file."""

    datestr = f"D:{date.year}"
    datestr += "".join(f"{val:02}" for val in (date.month, date.day) if val != 1)

    datestr += "".join(f"{val:02}" for val in (date.hour, date.minute, date.second) if val != 0)

    offset = date.utcoffset()
    if offset is None or offset.total_seconds() == 0:
        return datestr + "Z"

    offset_hours, offset_seconds = divmod(offset.total_seconds(), 3600)
    offset_minutes = int(offset_seconds / 60)

    return datestr + "'".join(f"{val:02}" for val in (offset_hours, offset_minutes))


def parse_iso8601(date_string: str) -> datetime.datetime:
    """Parses an ISO 6801 string into a :class:`datetime.datetime` object."""

    pattern = re.compile(
        r"""^(?P<year>\d{4})(?:-(?P<month>\d{2}))?(?:-(?P<day>\d{2}))? # yyyy-mm-dd
             (?:T(?P<hour>\d{2}):(?P<minute>\d{2})                     # hh-mm
             (?::(?P<second>\d{2})(?:\.(?P<fraction>\d+))?)?           # ss.s
             (?P<tzd>Z|[-+]\d{2}:\d{2})?)?$                            # Z or +hh:mm
        """,
        re.X,
    )

    mat = pattern.match(date_string)
    if not mat:
        raise ValueError(f"Expected an ISO 8601 string, received {date_string!r}")

    tzd = mat.group("tzd")
    if tzd is None or tzd == "Z":
        tz_offset = datetime.timedelta(hours=0, minutes=0)
    else:
        hh, mm = tzd.split(":")
        tz_offset = datetime.timedelta(hours=int(hh), minutes=int(mm))

    fraction_str = mat.group("fraction") or "0"
    fraction_micro = (int(fraction_str) / 10 ** len(fraction_str)) * 1_000_000

    return datetime.datetime(
        year=int(mat.group("year")),
        month=int(mat.group("month") or 1),
        day=int(mat.group("day") or 1),
        hour=int(mat.group("hour") or 0),
        minute=int(mat.group("minute") or 0),
        second=int(mat.group("second") or 0),
        microsecond=int(fraction_micro),
        tzinfo=datetime.timezone(tz_offset),
    )

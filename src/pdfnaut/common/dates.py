"""Utilities for parsing and encoding date formats: ISO 8601 and ISO 8824."""

from __future__ import annotations

import datetime
import re


def has_date(date: datetime.datetime) -> bool:
    """Returns whether ``date`` has a date component. In this case, if either the year,
    month or day isn't a default value."""
    return date.year > 1 or date.month > 1 or date.day > 1


def has_time(date: datetime.datetime) -> bool:
    """Returns whether ``date`` has a time component. In this case, if either the hour,
    minute, second or microsecond isn't a default value."""
    return date.hour > 0 or date.minute > 0 or date.second > 0 or date.microsecond > 0


def has_timezone(date: datetime.datetime) -> bool:
    """Returns whether ``date`` specifies a timezone other than UTC."""
    offset = date.utcoffset()
    return offset is not None and offset.total_seconds() != 0


def parse_iso8824(date_string: str) -> datetime.datetime:
    """Parses an ISO/IEC 8824 date string into a :class:`datetime.datetime` object
    (for example, ``D:20010727133720``).

    This is the type of date string described in § 7.9.4, "Dates" of the PDF spec.
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


def encode_iso8824(date: datetime.datetime, *, full: bool = True) -> str:
    """Encodes a :class:`datetime.datetime` object into an ISO 8824 date string suitable
    for storage in a PDF file.

    If ``full`` is True, this function will encode all date and time values. Otherwise,
    the function will perform partial encoding, only including components that aren't
    their default values.
    """

    datestr = f"D:{date.year}"

    if has_date(date) or full:
        datestr += f"{date.month:02}" if date.month > 1 or date.day > 1 or full else ""
        datestr += f"{date.day:02}" if date.day > 1 or date.second > 0 or full else ""

    if has_time(date) or has_timezone(date) or full:
        datestr += f"{date.hour:02}" if date.hour > 0 or date.minute > 0 or full else ""
        datestr += f"{date.minute:02}" if date.minute > 0 or date.second > 0 or full else ""
        datestr += f"{date.second:02}" if date.second > 0 or has_timezone(date) or full else ""

        offset = date.utcoffset()
        # If no offset, assume UTC
        if offset is None or offset.total_seconds() == 0:
            return datestr + "Z"

        offset_hours, offset_seconds = divmod(offset.total_seconds(), 3600)
        offset_minutes = int(offset_seconds / 60)

        return datestr + f"{offset_hours:+03n}'{offset_minutes:02}"

    return datestr


def parse_iso8601(date_string: str) -> datetime.datetime:
    """Parses a date string conforming to the ISO 8601 profile specified in
    https://www.w3.org/TR/NOTE-datetime into a :class:`datetime.datetime` object."""

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
        microsecond=round(fraction_micro),
        tzinfo=datetime.timezone(tz_offset),
    )


def encode_iso8601(date: datetime.datetime, *, full: bool = True) -> str:
    """Encodes a :class:`datetime.datetime` object into a date string conforming to the
    ISO 6801 profile specified in https://www.w3.org/TR/NOTE-datetime.

    If ``full`` is True, this function will encode all date and time values. Otherwise,
    the function will perform partial encoding, only including components that aren't
    their default values.
    """

    datestr = str(date.year)

    if has_date(date) or full:
        datestr += f"-{date.month:02}"
        # Append day if present or if hour present
        datestr += f"-{date.day:02}" if date.day > 1 or date.hour > 0 or full else ""

    if has_time(date) or has_timezone(date) or full:
        datestr += f"T{date.hour:02}:{date.minute:02}"

        # Whether we have a second
        if date.second > 0 or date.microsecond > 0 or full:
            datestr += f":{date.second:02}"
            datestr += f".{date.microsecond:06n}" if date.microsecond > 0 else ""

        offset = date.utcoffset()
        # If no offset, assume UTC
        if offset is None or offset.total_seconds() == 0:
            return datestr + "Z"

        offset_hours, offset_seconds = divmod(offset.total_seconds(), 3600)
        offset_minutes = int(offset_seconds / 60)

        return datestr + f"{offset_hours:+03n}:{offset_minutes:02}"

    return datestr

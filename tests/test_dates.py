# Unit tests for parsing and decoding datetime formats

from __future__ import annotations

import datetime

from pdfnaut.common.dates import encode_iso8601, encode_iso8824, parse_iso8601, parse_iso8824


def test_parse_iso8824() -> None:
    # Some examples from the spec
    assert parse_iso8824("D:199812231952-08'00") == datetime.datetime(
        1998, 12, 23, 19, 52, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-8, minutes=0))
    )
    assert parse_iso8824("D:20010727133720") == datetime.datetime(
        2001, 7, 27, 13, 37, 20, tzinfo=datetime.timezone.utc
    )

    # Only date
    assert parse_iso8824("D:19981223Z") == datetime.datetime(
        1998, 12, 23, 0, 0, 0, tzinfo=datetime.timezone.utc
    )

    # Date string with ending apostrophe (pre 2.0)
    assert parse_iso8824("D:2024'") == datetime.datetime(
        2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
    )


def test_encode_iso8824():
    # Date and time
    assert encode_iso8824(datetime.datetime(2001, 7, 27, 13, 37, 20)) == "D:20010727133720Z"

    # Only date
    assert encode_iso8824(datetime.datetime(2001, 7, 27), full=False) == "D:20010727"

    # With timezone
    tzd = datetime.timezone(datetime.timedelta(hours=-6, minutes=0))
    assert (
        encode_iso8824(datetime.datetime(2001, 7, 27, 13, 37, 20, tzinfo=tzd))
        == "D:20010727133720-06'00"
    )


def test_parse_iso8601() -> None:
    # Only year
    assert parse_iso8601("2025") == datetime.datetime(
        2025, 1, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    # Date
    assert parse_iso8601("2025-02-01") == datetime.datetime(
        2025, 2, 1, 0, 0, tzinfo=datetime.timezone.utc
    )
    # Date and time without seconds
    assert parse_iso8601("2025-02-01T12:31") == datetime.datetime(
        2025, 2, 1, 12, 31, tzinfo=datetime.timezone.utc
    )
    # Date and time with seconds
    assert parse_iso8601("2025-02-01T12:31:17") == datetime.datetime(
        2025, 2, 1, 12, 31, 17, tzinfo=datetime.timezone.utc
    )
    # Date and time with seconds and fraction unit
    assert parse_iso8601("2025-02-01T12:31:17.20") == datetime.datetime(
        2025, 2, 1, 12, 31, 17, 200_000, tzinfo=datetime.timezone.utc
    )
    # Date and time with seconds, fraction unit, and timezone
    tzd = datetime.timezone(datetime.timedelta(hours=-6, minutes=0))
    assert parse_iso8601("2025-02-01T12:31:17.20-06:00") == datetime.datetime(
        2025, 2, 1, 12, 31, 17, 200_000, tzd
    )


def test_encode_iso8601():
    # Date and time
    assert encode_iso8601(datetime.datetime(2001, 7, 27, 13, 37, 20)) == "2001-07-27T13:37:20Z"

    # Datetime with timezone
    tzd = datetime.timezone(datetime.timedelta(hours=-6, minutes=0))
    assert (
        encode_iso8601(datetime.datetime(2025, 2, 1, 12, 31, 17, 200_000, tzd))
        == "2025-02-01T12:31:17.200000-06:00"
    )

    # Only date
    assert encode_iso8601(datetime.datetime(2024, 10, 20), full=False) == "2024-10-20"

    # Date and time (utc)
    assert encode_iso8601(datetime.datetime(2024, 10, 20, 15, 34, 10)) == "2024-10-20T15:34:10Z"

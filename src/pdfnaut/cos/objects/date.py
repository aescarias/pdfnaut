import datetime
import re
from typing import Literal, NamedTuple, cast
from typing_extensions import Self


DateOffset = Literal["+", "-", "Z"]


class PdfDate(NamedTuple):
    """A date value stored in a PDF document (``§ 7.9.4 Dates``)"""

    year: int 
    month: int = 1
    day: int = 1 
    hour: int = 0
    minute: int = 0
    second: int = 0
    offset: DateOffset = "Z"
    offset_hour: int = 0
    offset_minute: int = 0
    
    @classmethod
    def from_pdf(cls, date: str) -> Self:
        """Creates a :class:`PdfDate` from a PDF date string (for example: ``D:20010727133720``)."""
        # pdf 1.7 (and below) dates may end with an apostrophe
        if date.endswith("'"):
            date = date[:-1]

        pattern = re.compile(
            r"""^D:(?P<year>\d{4})(?P<month>\d{2})?(?P<day>\d{2})? # date
                    (?P<hour>\d{2})?(?P<minute>\d{2})?(?P<second>\d{2})? # time
                    (?P<offset>[-+Z])?(?P<offset_hour>\d{2})?(?P<offset_minute>'\d{2})?$ # offset
            """, 
            re.X
        )

        mat = pattern.match(date)
        if not mat:
            raise ValueError("Invalid date format")

        return cls(
            year=int(mat.group("year")), 
            month=int(mat.group("month") or 1), 
            day=int(mat.group("day") or 1), 
            hour=int(mat.group("hour") or 0), 
            minute=int(mat.group("minute") or 0), 
            second=int(mat.group("second") or 0), 
            offset=cast(DateOffset, mat.group("offset") or "Z"),
            offset_hour=int(mat.group("offset_hour") or 0),
            offset_minute=int((mat.group("offset_minute") or "'0")[1:])
        )    
    
    def as_datetime(self) -> datetime.datetime:
        """Returns the :class:`datetime.datetime` equivalent of this date."""
        if self.offset == "Z" or self.offset == "+":
            delta = datetime.timedelta(hours=self.offset_hour, minutes=self.offset_minute)
        else:
            delta = datetime.timedelta(hours=-self.offset_hour, minutes=self.offset_minute)

        return datetime.datetime(
            self.year, self.month, self.day, self.hour, self.minute, self.second, 
            tzinfo=datetime.timezone(delta))
    
    def as_pdf_string(self) -> str:
        """Returns the PDF equivalent of this date as a string."""
        datestr = f"D:{self.year}"
        datestr += "".join(str(val) for val in (self.month, self.day) if val != 1)
        
        datestr += "".join(str(val) for val in (self.hour, self.minute, self.second) if val != 0)

        if self.offset == "Z":
            return datestr 
        
        return datestr + "'".join(str(val) for val in (self.offset_hour, self.offset_minute) if val != 0)

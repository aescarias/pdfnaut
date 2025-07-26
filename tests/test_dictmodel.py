from __future__ import annotations

from typing import Literal, Union

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.cos.objects import PdfDictionary

NumberingStyle = Literal["D", "R", "r", "A", "a"]


def test_basic_dictmodel() -> None:
    @dictmodel()
    class Point(PdfDictionary):
        x: int
        y: int
        z: Union[int, None] = None

    assert hasattr(Point, "__accessors__")

    p = Point(x=10, y=20)
    assert p.data == {"X": 10, "Y": 20}

    p.z = -10
    assert "Z" in p.data and p["Z"] == -10


def test_dictmodel_with_defaults() -> None:
    @dictmodel()
    class PageLabelScheme(PdfDictionary):
        style: Union[NumberingStyle, None] = field("S", default=None)
        prefix: Union[str, None] = field("P", default=None)
        start: int = field("St", default=1)

    scheme = PageLabelScheme(style="D")
    assert scheme.style == "D" and scheme.prefix is None and scheme.start == 1

    scheme["St"] = 10
    assert scheme.start == 10


def test_inherited_dictmodel() -> None:
    @dictmodel()
    class Point2D(PdfDictionary):
        x: int
        y: int

    @dictmodel()
    class Point3D(Point2D):
        z: int

    p2 = Point2D(10, 20)
    assert p2.data == {"X": 10, "Y": 20}

    p3 = Point3D(10, 20, 30)
    assert p3.data == {"X": 10, "Y": 20, "Z": 30}

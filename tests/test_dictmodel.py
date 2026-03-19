from enum import IntEnum
from typing import Literal, Union

from typing_extensions import Self

from pdfnaut.common.dictmodels import dictmodel, field
from pdfnaut.cos.objects import PdfArray, PdfDictionary, PdfName

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


def test_dictmodel_default_factory() -> None:
    @dictmodel
    class OutlineItem(PdfDictionary):
        title: str = field("T")
        color: PdfArray[float] = field("C", default_factory=lambda: PdfArray([0, 0, 0]))

    item_1 = OutlineItem("Title")

    assert item_1.title == "Title" and item_1.color == PdfArray([0, 0, 0])

    item_2 = OutlineItem("Another Title", PdfArray([0.5, 0.5, 0.5]))
    assert item_2.data["T"] == b"Another Title" and item_2.data["C"] == PdfArray([0.5, 0.5, 0.5])


def test_dictmodel_post_init() -> None:
    @dictmodel
    class GeoCoordSystem(PdfDictionary):
        epsg: int | None = field("EPSG", default=None)
        wkt: str | None = field("WKT", default=None)

        def __post_init__(self) -> None:
            self["Type"] = PdfName(b"GEOGCS")

    gcs = GeoCoordSystem(epsg=4122)
    assert gcs["EPSG"] == 4122 and gcs["Type"] == PdfName(b"GEOGCS")


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


def test_dictmodel_model() -> None:
    @dictmodel
    class Foo(PdfDictionary):
        bar: int
        baz: int

        @classmethod
        def from_dict(cls, mapping: PdfDictionary) -> Self:
            foo = cls(0, 0)
            foo.data = mapping.data
            return foo

    @dictmodel
    class FooWrap(PdfDictionary):
        foo: Foo

        @classmethod
        def from_dict(cls, mapping: PdfDictionary) -> Self:
            wrap = cls(Foo(0, 0))
            wrap.data = mapping.data
            return wrap

    foo = Foo(bar=10, baz=20)
    wrap = FooWrap(foo)

    assert wrap.foo == foo
    assert wrap.data["Foo"] == foo.data


def test_dictmodel_transform() -> None:
    class Color(IntEnum):
        NONE = 0
        RED = 1
        GREEN = 2
        BLUE = 3

    @dictmodel
    class Bar(PdfDictionary):
        color: Color = field(encoder=int, decoder=Color)

    bar = Bar(Color.RED)
    assert bar.color == Color.RED
    assert bar.data["Color"] == 1

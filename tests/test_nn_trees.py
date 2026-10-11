# Unit tests for parsing number and name trees
from __future__ import annotations

import pytest

from pdfnaut.cos.lexer import PdfLexer
from pdfnaut.cos.object_parser import PdfObjectParser
from pdfnaut.cos.objects import PdfArray, PdfDictionary, PdfName
from pdfnaut.cos.objects.trees import NameTree, NumberTree


def _parse_dictionary(data: bytes) -> PdfDictionary:
    parser = PdfObjectParser(PdfLexer(data))
    result = parser.next_object()
    assert isinstance(result, PdfDictionary)
    return result


def test_number_tree() -> None:
    tree_map = _parse_dictionary(
        b"""
        << /Kids [<< /Limits [1 3]
                     /Nums [1 /Name 2 (String) 3 10] >>
                  << /Limits [4 6]
                     /Nums [4 (abc) 5 /Type 6 (def)] >>
                 ]
        >>
        """
    )
    tree = NumberTree.from_dict(tree_map)

    assert tree[3] == 10
    assert tree[5] == PdfName(b"Type")

    with pytest.raises(KeyError):
        tree[7]


def test_name_tree() -> None:
    tree_map = _parse_dictionary(
        b"""
        << /Kids [<< /Limits [(A) (C)]
                     /Names [(A) /Name (B) (String) (C) 10] >>
                  << /Limits [(D) (F)]
                     /Names [(D) (abc) (E) /Type (F) (def)] >>
                 ]
        >>
        """
    )
    tree = NameTree.from_dict(tree_map)

    assert tree[b"C"] == 10
    assert tree[b"F"] == b"def"

    with pytest.raises(KeyError):
        tree[b"X"]


def test_name_tree_items_write_through() -> None:
    tree = NameTree(items={b"A": PdfName(b"One"), b"B": PdfName(b"Two")})

    names = tree.names
    assert names is not None

    names[b"A"] = PdfName(b"Updated")
    names[b"C"] = PdfName(b"Three")
    del names[b"B"]

    assert tree._raw["Names"] == PdfArray([b"A", PdfName(b"Updated"), b"C", PdfName(b"Three")])


def test_number_tree_items_write_through() -> None:
    tree = NumberTree(items={1: PdfName(b"One"), 2: PdfName(b"Two")})

    nums = tree.nums
    assert nums is not None

    nums[1] = PdfName(b"Updated")
    nums[3] = PdfName(b"Three")
    del nums[2]

    assert tree._raw["Nums"] == PdfArray([1, PdfName(b"Updated"), 3, PdfName(b"Three")])


def test_number_tree_items_sorted() -> None:
    tree = NumberTree()
    tree.nums = {5: b"five", 1: b"one", 3: b"three"}

    assert tree._raw["Nums"] == PdfArray([1, b"one", 3, b"three", 5, b"five"])

    nums = tree.nums
    assert nums is not None
    nums[2] = b"two"
    assert tree._raw["Nums"] == PdfArray([1, b"one", 2, b"two", 3, b"three", 5, b"five"])


def test_name_tree_items_sorted() -> None:
    tree = NameTree()
    tree.names = {b"Z": b"zee", b"A": b"aye", b"M": b"em"}

    assert tree._raw["Names"] == PdfArray([b"A", b"aye", b"M", b"em", b"Z", b"zee"])

    names = tree.names
    assert names is not None
    names[b"B"] = b"bee"
    assert tree._raw["Names"] == PdfArray([b"A", b"aye", b"B", b"bee", b"M", b"em", b"Z", b"zee"])


def test_number_tree_nums_assignment_source_tracked() -> None:
    tree = NumberTree()
    values = {0: b"Hello, world!"}

    tree.nums = values

    assert tree.nums == {0: b"Hello, world!"}

    values[0] = b"beep"

    assert tree.nums == {0: b"beep"}
    assert tree[0] == b"beep"


def test_number_tree_kids_assignment_source_tracked() -> None:
    tree = NumberTree()
    kids = [NumberTree(items={0: b"A"})]

    tree.kids = kids

    assert len(tree.kids or []) == 1
    assert tree.kids is not None
    assert tree.kids[0].nums == {0: b"A"}

    kids.append(NumberTree(items={1: b"B"}))

    assert len(tree.kids or []) == 2
    assert tree.kids is not None
    assert tree.kids[1].nums == {1: b"B"}


def test_set_item_on_empty_nn_tree() -> None:
    num_tree = NumberTree()
    num_tree[0] = b"abc"
    assert num_tree[0] == b"abc"
    assert num_tree._raw["Nums"] == PdfArray([0, b"abc"])

    name_tree = NameTree()
    name_tree[b"abc"] = b"def"
    assert name_tree[b"abc"] == b"def"
    assert name_tree._raw["Names"] == PdfArray([b"abc", b"def"])

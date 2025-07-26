from __future__ import annotations

from inspect import getattr_static
from typing import Any, TypeVar, cast

from typing_extensions import dataclass_transform, get_type_hints

from ..cos.objects.containers import PdfDictionary
from .accessors import MISSING, Accessor, lookup_accessor

_T = TypeVar("_T")


class Field:
    def __init__(
        self,
        key: str | None = None,
        default: Any = MISSING,
        init: bool | None = None,
        repr_: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        # To be filled in later
        self.name: str | None = None
        self.type_: type | None = None

        self._key = key
        self.default = default
        self.init = init
        self.repr_ = repr_
        self.metadata = metadata

    @property
    def key(self) -> str:
        if self._key is None:
            raise ValueError(f"No key assigned for field {self.name!r}.")

        return self._key


def field(
    key: str | None = None,
    default: Any = MISSING,
    init: bool | None = None,
    repr_: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    """Defines a field in a dictmodel.

    Arguments:
        key (str, optional):
            The name of the key that will be accessed by this field. If not specified,
            the key will be the title-cased version of the field name.

        default (Any, optional):
            The default value of the field if it is not specified. If no default is
            specified, the field is assumed to be required.

        init (bool | None, optional):
            Whether this field will appear as part of the class constructor. If not specified,
            it defaults to the value of the ``init`` argument in the dictmodel.

        repr_ (bool | None, optional):
            Whether this field will appear as part of the class representation.
            If not specified, it defaults to the value of the ``repr_`` argument
            in the dictmodel.

        metadata (dict[str, Any], optional):
            Additional metadata for this field which may be used by the accessor.
    """
    return Field(key, default, init, repr_, metadata)


T = TypeVar("T")


def defaultize(cls: type[T]) -> T:
    """Returns an instance of a dictmodel ``cls`` initialized with default values."""
    accessors = getattr(cls, "__accessors__", MISSING)
    if accessors is MISSING:
        raise TypeError(f"type {cls!r} is not a dictmodel")

    mapping: dict[str, Any] = {}
    for acc in cast(list[Accessor], accessors):
        assert acc.field.name is not None
        if not acc.field.init:
            continue

        if acc.field.default is not MISSING:
            mapping[acc.field.name] = acc.field.default
        else:
            mapping[acc.field.name] = None

    return cls(**mapping)


def snake_to_title_case(value: str) -> str:
    return "".join(val.title() for val in value.split("_"))


T = TypeVar("T")


def build_repr(cls: type[T], repr_accessors: list[Accessor]):
    def _repr(self: T) -> str:
        attrs = []

        for acc in repr_accessors:
            assert acc.field.name is not None

            value = getattr(self, acc.field.name, acc.field.default)
            if value == acc.field.default:
                continue

            attrs.append(f"{acc.field.name}={value!r}")

        return f"{cls.__name__}({', '.join(attrs)})"

    return _repr


def create_accessors(cls, *, parent_init: bool = True, parent_repr: bool = True) -> list[Accessor]:
    accessors = []

    for attr, type_ in get_type_hints(cls, include_extras=True).items():
        default = getattr_static(cls, attr, MISSING)

        if isinstance(default, Field):
            model_field = default
        elif hasattr(default, "field"):
            # inherited field from an accessor
            model_field = default.field
        else:
            model_field = Field(default=default)

        if model_field._key is None:
            model_field._key = snake_to_title_case(attr)

        model_field.name = attr
        model_field.type_ = type_
        if model_field.init is None:
            model_field.init = parent_init

        if model_field.repr_ is None:
            model_field.repr_ = parent_repr

        accessor, metadata = lookup_accessor(type_)
        if accessor is None:
            raise ValueError(f"No accessor registered for type {type_!r}")

        if metadata is not None:
            if model_field.metadata is not None:
                model_field.metadata |= metadata
            else:
                model_field.metadata = metadata

        accessors.append(accessor(model_field))

    return accessors


@dataclass_transform(field_specifiers=(field,))
def dictmodel(*, init: bool = True, repr_: bool = True):
    def wrapper(cls: type[_T]) -> type[_T]:
        if not issubclass(cls, PdfDictionary):
            raise TypeError("cls must be a subclass of PdfDictionary")

        accessors = create_accessors(cls, parent_init=init, parent_repr=repr_)

        init_args = ["self"]

        for accessor in accessors:
            assert accessor.field.name is not None

            setattr(cls, accessor.field.name, accessor)

            if not accessor.field.init:
                continue

            init_arg_string = accessor.field.name
            if accessor.field.default is not MISSING:
                init_arg_string += f" = {accessor.field.default!r}"

            init_args.append(init_arg_string)

        required_subcls_args = []
        for acc in getattr(cls, "__accessors__", []):
            if not acc.field.init:
                continue

            if acc.field.default is not MISSING:
                required_subcls_args.append(f"{acc.field.name}={acc.field.name}")
            else:
                required_subcls_args.append(acc.field.name)

        init_fn_body = [
            f"def __init__({', '.join(init_args)}):",
            f"  super({cls.__name__}, self).__init__({', '.join(required_subcls_args)})",
        ]

        for acc in accessors:
            if not acc.field.init:
                continue

            init_fn_body.append(f"  self.{acc.field.name} = {acc.field.name}\n")

        repr_fn = build_repr(cls, [acc for acc in accessors if acc.field.repr_])
        namespace = {}

        exec("\n".join(init_fn_body), {cls.__name__: cls}, namespace)

        if "__init__" not in cls.__dict__:
            cls.__init__ = namespace["__init__"]
            cls.__init__.__name__ = "__init__"
            cls.__init__.__qualname__ = f"{cls.__qualname__}.__init__"

        if "__repr__" not in cls.__dict__:
            cls.__repr__ = repr_fn
            cls.__repr__.__name__ = "__repr__"
            cls.__repr__.__qualname__ = f"{cls.__qualname__}.__repr__"

        setattr(cls, "__accessors__", accessors)

        return cls

    return wrapper

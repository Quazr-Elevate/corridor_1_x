"""Shared Pydantic building blocks."""
from __future__ import annotations

import re
from typing import Annotated, Any, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel

from app.shared.countries import to_alpha2


class CamelModel(BaseModel):
    """Base schema — fields declared snake_case, serialized as camelCase.

    Matches the frontend contract (see frontend/lib/api.ts). Requests can
    arrive with either casing thanks to populate_by_name=True.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class RequestModel(CamelModel):
    """Base for request bodies: a field the API does not know is refused.

    Silently dropping it hides client bugs and lets a caller believe it set
    something (a status, an owner) that was never read. The API answers 422
    ``request.unknown_field`` instead.
    """

    model_config = ConfigDict(extra="forbid")


T = TypeVar("T")


class ItemList(CamelModel, Generic[T]):
    """Every collection is returned as ``{items, total}``, never a bare array,
    so paging can be added without breaking a client (decision A-024)."""

    total: int
    items: list[T]


def item_list(items: list[T]) -> ItemList[T]:
    """Wrap a complete, unpaged collection."""
    return ItemList(total=len(items), items=items)


def _drop_blank_items(v: Any) -> Any:
    if isinstance(v, list):
        return [x for x in v if not (isinstance(x, str) and not x.strip())]
    return v


def _to_alpha2(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    code = to_alpha2(v) if len(v.strip()) <= 3 else None
    if code is None:
        raise ValueError(f"{v.strip()[:12]!r} isn't a country we recognise. Choose a country from the list.")
    return code


#: ISO-3166 alpha-2 code. Alpha-3 input ("IND") is accepted and converted.
CountryCode = Annotated[str, BeforeValidator(_to_alpha2), StringConstraints(min_length=2, max_length=2)]

#: A list input where blank strings are silently dropped (UI sends "" rows).
CountryList = Annotated[list[CountryCode], BeforeValidator(_drop_blank_items)]
TagList = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]],
    BeforeValidator(_drop_blank_items),
]


# An HTML tag: "<script>", "</b>", "<img src=x onerror=…>", "<!-- … -->".
# A comparison such as "moisture < 12% and > 5%" is not one.
_MARKUP = re.compile(r"<\s*/?\s*[a-z!][^<>]*>", re.I)


def _no_markup(v: str) -> str:
    """Plain text only. The SPA escapes, but these values also reach
    emails, PDFs, CSV exports and the audit log, where nothing escapes them."""
    if _MARKUP.search(v):
        raise ValueError("Use plain text: remove the < > tags.")
    return v


def text(max_length: int, min_length: int = 0) -> Any:
    """Trimmed plain text with length bounds; HTML tags are refused
    (``Annotated`` alias factory)."""
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length),
        AfterValidator(_no_markup),
    ]

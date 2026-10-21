"""Shared Pydantic building blocks."""
from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints
from pydantic.alias_generators import to_camel

from app.shared.countries import to_alpha2


class CamelModel(BaseModel):
    """Base schema — fields declared snake_case, serialized as camelCase.

    Matches the frontend contract (see frontend/lib/api.ts). Requests can
    arrive with either casing thanks to populate_by_name=True.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


def _drop_blank_items(v: Any) -> Any:
    if isinstance(v, list):
        return [x for x in v if not (isinstance(x, str) and not x.strip())]
    return v


def _to_alpha2(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    code = to_alpha2(v) if len(v.strip()) <= 3 else None
    if code is None:
        raise ValueError(f"Unknown country code: {v.strip()[:12]!r} (use ISO 3166-1 alpha-2, e.g. IN).")
    return code


#: ISO-3166 alpha-2 code. Alpha-3 input ("IND") is accepted and converted.
CountryCode = Annotated[str, BeforeValidator(_to_alpha2), StringConstraints(min_length=2, max_length=2)]

#: A list input where blank strings are silently dropped (UI sends "" rows).
CountryList = Annotated[list[CountryCode], BeforeValidator(_drop_blank_items)]
TagList = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]],
    BeforeValidator(_drop_blank_items),
]


def text(max_length: int, min_length: int = 0) -> Any:
    """Trimmed string with length bounds (``Annotated`` alias factory)."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)]

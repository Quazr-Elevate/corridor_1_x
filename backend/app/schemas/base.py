from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base schema — fields declared snake_case, serialized as camelCase.

    Matches the frontend contract (see frontend/lib/api.ts). Requests can
    arrive with either casing thanks to populate_by_name=True.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)

from app.schemas.base import CamelModel


class PanLookup(CamelModel):
    pan: str
    name: str

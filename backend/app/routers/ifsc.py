from fastapi import APIRouter, HTTPException

from app.providers.ifsc import IfscNotFound, IfscServiceError, lookup_ifsc
from app.schemas.me import IfscLookup

router = APIRouter(prefix="/ifsc", tags=["ifsc"])


@router.get("/{ifsc}", response_model=IfscLookup, response_model_by_alias=True)
async def get_ifsc(ifsc: str) -> IfscLookup:
    try:
        data = await lookup_ifsc(ifsc)
    except IfscNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except IfscServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return IfscLookup(**data)

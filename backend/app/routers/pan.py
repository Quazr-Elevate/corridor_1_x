from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.seller import Seller
from app.schemas.pan import PanLookup
from app.validators import PAN_REGEX

router = APIRouter(prefix="/pan", tags=["pan"])

# Stub for now — Masters India also offers a PAN verification API which can be
# wired here later (env var: MASTERS_INDIA_ACCESS_TOKEN already exists).
_NAME_BY_CHAR: dict[str, str] = {
    "A": "Aarav Sharma", "B": "Bharat Iyer", "C": "Chetan Nair", "D": "Devang Patel",
    "E": "Ekansh Rao", "F": "Farhan Khan", "G": "Gaurav Menon", "H": "Harsh Verma",
    "I": "Ishaan Rao", "J": "Jayesh Bhat", "K": "Karthik Reddy", "L": "Lakshay Singh",
    "M": "Manish Gupta", "N": "Nikhil Desai", "O": "Om Prakash", "P": "Pranav Kulkarni",
    "Q": "Qadir Sheikh", "R": "Rahul Joshi", "S": "Siddharth Mehta", "T": "Tanmay Shah",
    "U": "Utkarsh Rai", "V": "Vikram Nair", "W": "Wasim Ali", "X": "Xavier D'Souza",
    "Y": "Yash Agarwal", "Z": "Zeeshan Malik",
}


@router.get("/{pan}", response_model=PanLookup, response_model_by_alias=True)
async def get_pan(pan: str, db: AsyncSession = Depends(get_db)) -> PanLookup:
    clean = pan.strip().upper()
    if not PAN_REGEX.match(clean):
        raise HTTPException(status_code=400, detail="Enter a valid 10-character PAN")

    # Reject duplicates upfront. sellers.pan is populated on both onboarding
    # paths (derived from GSTIN chars 3–12 on the GSTIN flow, entered directly
    # on the PAN flow), so this catches conflicts across both.
    existing = await db.scalar(select(Seller).where(Seller.pan == clean))
    if existing:
        raise HTTPException(status_code=409, detail="This PAN is already registered")

    return PanLookup(pan=clean, name=_NAME_BY_CHAR.get(clean[0], "Aarav Sharma"))

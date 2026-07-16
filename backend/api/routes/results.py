"""Results endpoint — legacy alias for /leads, kept for backwards compatibility."""
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage import crud

router = APIRouter(prefix="/results", tags=["results"])


class LeadResponse(BaseModel):
    id: int
    job_id: int
    name: Optional[str]
    category: Optional[str]
    description: Optional[str]
    industry: Optional[str]
    employee_count: Optional[str]
    city: Optional[str]
    country: Optional[str]
    website: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    facebook: Optional[str]
    instagram: Optional[str]
    linkedin: Optional[str]
    twitter: Optional[str]
    youtube: Optional[str]
    status: Optional[str]
    score: Optional[int]
    email_verified: Optional[bool]
    source: Optional[str]
    source_url: Optional[str]
    created_at: Optional[str]
    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=LeadListResponse)
async def list_results(
    job_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    has_phone: bool = Query(False),
    has_email: bool = Query(False),
    has_website: bool = Query(False),
    has_address: bool = Query(False),
    has_social: bool = Query(False),
    status: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    tags: Optional[str] = Query(None),
    list_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    items, total = await crud.get_leads(
        db, job_id=job_id, page=page, page_size=page_size,
        has_phone=has_phone, has_email=has_email, has_website=has_website,
        has_address=has_address, has_social=has_social,
        status=status, min_score=min_score, tags=tag_list,
        list_id=list_id, search=search, sort_by=sort_by, sort_dir=sort_dir,
    )

    def _resp(item):
        excluded = {"updated_at", "created_at", "founded_year", "email_verified"}
        return LeadResponse(
            **{c.name: getattr(item, c.name) for c in item.__table__.columns
               if c.name not in excluded},
            email_verified=item.email_verified,
            created_at=item.created_at.isoformat() if item.created_at else None,
        )

    return LeadListResponse(
        items=[_resp(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )

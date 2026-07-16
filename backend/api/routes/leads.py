"""
Lead CRM endpoints — status, notes, tags, activity, email verification,
LinkedIn enrichment, bulk actions, lead lists, saved searches.
"""
import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage import crud
from storage.models import Lead

router = APIRouter(tags=["leads"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class LeadResponse(BaseModel):
    id: int
    job_id: int
    name: Optional[str]
    category: Optional[str]
    description: Optional[str]
    industry: Optional[str]
    employee_count: Optional[str]
    founded_year: Optional[str]
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
    updated_at: Optional[str]
    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class NoteResponse(BaseModel):
    id: int
    lead_id: int
    content: str
    created_at: Optional[str]
    model_config = {"from_attributes": True}


class ListResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    member_count: int
    created_at: Optional[str]
    model_config = {"from_attributes": True}


class SavedSearchResponse(BaseModel):
    id: int
    name: str
    query: str
    last_run_at: Optional[str]
    last_result_count: int
    created_at: Optional[str]
    model_config = {"from_attributes": True}


class ActivityResponse(BaseModel):
    id: int
    lead_id: int
    action: str
    detail: Optional[str]
    created_at: Optional[str]
    model_config = {"from_attributes": True}


def _lead_resp(lead: Lead) -> LeadResponse:
    return LeadResponse(
        **{c.name: getattr(lead, c.name) for c in lead.__table__.columns
           if c.name not in ("created_at", "updated_at")},
        created_at=lead.created_at.isoformat() if lead.created_at else None,
        updated_at=lead.updated_at.isoformat() if lead.updated_at else None,
    )


# ── Single lead ───────────────────────────────────────────────────────────────

@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    lead = await crud.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return _lead_resp(lead)


# ── Lead list (advanced filtering) ───────────────────────────────────────────

@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
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
    max_score: Optional[int] = Query(None, ge=0, le=100),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
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
        status=status, min_score=min_score, max_score=max_score,
        tags=tag_list, list_id=list_id, search=search,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    return LeadListResponse(
        items=[_lead_resp(i) for i in items],
        total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


# ── Status ────────────────────────────────────────────────────────────────────

@router.patch("/leads/{lead_id}/status", response_model=LeadResponse)
async def set_status(
    lead_id: int,
    status: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    valid = {"new", "contacted", "qualified", "rejected", "won", "lost"}
    if status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")
    lead = await crud.update_lead_status(db, lead_id, status)
    if not lead:
        raise HTTPException(404, "Lead not found")
    from storage import crud as c
    await c._log(db, lead_id, "status_changed", status)
    await db.commit()
    return _lead_resp(lead)


# ── Notes ─────────────────────────────────────────────────────────────────────

@router.get("/leads/{lead_id}/notes", response_model=List[NoteResponse])
async def get_notes(lead_id: int, db: AsyncSession = Depends(get_db)):
    notes = await crud.get_notes(db, lead_id)
    return [NoteResponse(
        id=n.id, lead_id=n.lead_id, content=n.content,
        created_at=n.created_at.isoformat() if n.created_at else None,
    ) for n in notes]


@router.post("/leads/{lead_id}/notes", response_model=NoteResponse)
async def add_note(
    lead_id: int,
    content: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    note = await crud.add_note(db, lead_id, content)
    await db.commit()
    return NoteResponse(
        id=note.id, lead_id=note.lead_id, content=note.content,
        created_at=note.created_at.isoformat() if note.created_at else None,
    )


@router.delete("/leads/{lead_id}/notes/{note_id}")
async def delete_note(lead_id: int, note_id: int, db: AsyncSession = Depends(get_db)):
    await crud.delete_note(db, note_id)
    await db.commit()
    return {"ok": True}


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get("/leads/{lead_id}/tags", response_model=List[str])
async def get_tags(lead_id: int, db: AsyncSession = Depends(get_db)):
    return await crud.get_tags(db, lead_id)


@router.post("/leads/{lead_id}/tags")
async def add_tag(
    lead_id: int,
    tag: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    await crud.add_tag(db, lead_id, tag)
    await db.commit()
    return {"tags": await crud.get_tags(db, lead_id)}


@router.delete("/leads/{lead_id}/tags/{tag}")
async def remove_tag(lead_id: int, tag: str, db: AsyncSession = Depends(get_db)):
    await crud.remove_tag(db, lead_id, tag)
    await db.commit()
    return {"tags": await crud.get_tags(db, lead_id)}


@router.get("/tags", response_model=List[str])
async def all_tags(db: AsyncSession = Depends(get_db)):
    return await crud.get_all_tags(db)


# ── Activity ──────────────────────────────────────────────────────────────────

@router.get("/leads/{lead_id}/activity", response_model=List[ActivityResponse])
async def get_activity(lead_id: int, db: AsyncSession = Depends(get_db)):
    logs = await crud.get_activity(db, lead_id)
    return [ActivityResponse(
        id=l.id, lead_id=l.lead_id, action=l.action, detail=l.detail,
        created_at=l.created_at.isoformat() if l.created_at else None,
    ) for l in logs]


# ── Email verification ────────────────────────────────────────────────────────

@router.post("/leads/{lead_id}/verify-email")
async def verify_email(lead_id: int, db: AsyncSession = Depends(get_db)):
    lead = await crud.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if not lead.email:
        raise HTTPException(400, "Lead has no email address")
    result = await crud.verify_email(db, lead_id, lead.email)
    await db.commit()
    return {"verified": result, "email": lead.email}


# ── LinkedIn enrichment ───────────────────────────────────────────────────────

@router.post("/leads/{lead_id}/enrich-linkedin", response_model=LeadResponse)
async def enrich_linkedin(lead_id: int, db: AsyncSession = Depends(get_db)):
    lead = await crud.get_lead(db, lead_id)
    if not lead or not lead.name:
        raise HTTPException(404, "Lead not found or has no name")
    from api.services.linkedin_enricher import enrich_from_search
    updates = await enrich_from_search(lead.name, lead.city or lead.address or "")
    if updates:
        lead = await crud.update_lead_fields(db, lead_id, updates)
        await crud._log(db, lead_id, "linkedin_enriched",
                        f"industry={updates.get('industry')} employees={updates.get('employee_count')}")
        await db.commit()
    return _lead_resp(lead)


# ── Bulk actions ──────────────────────────────────────────────────────────────

class BulkActionRequest(BaseModel):
    lead_ids: List[int]
    action: str             # set_status / add_tag / remove_tag / add_to_list / delete
    value: Optional[str] = None
    list_id: Optional[int] = None


@router.post("/leads/bulk")
async def bulk_action(req: BulkActionRequest, db: AsyncSession = Depends(get_db)):
    if not req.lead_ids:
        raise HTTPException(400, "No lead_ids provided")

    if req.action == "set_status":
        if not req.value:
            raise HTTPException(400, "value required for set_status")
        await crud.bulk_update_leads(db, req.lead_ids, {"status": req.value})

    elif req.action == "add_tag":
        if not req.value:
            raise HTTPException(400, "value required for add_tag")
        for lid in req.lead_ids:
            await crud.add_tag(db, lid, req.value)

    elif req.action == "remove_tag":
        if not req.value:
            raise HTTPException(400, "value required for remove_tag")
        for lid in req.lead_ids:
            await crud.remove_tag(db, lid, req.value)

    elif req.action == "add_to_list":
        if not req.list_id:
            raise HTTPException(400, "list_id required for add_to_list")
        await crud.add_to_list(db, req.list_id, req.lead_ids)

    elif req.action == "delete":
        await crud.delete_leads(db, req.lead_ids)

    else:
        raise HTTPException(400, f"Unknown action: {req.action}")

    await db.commit()
    return {"ok": True, "affected": len(req.lead_ids)}


# ── Lead Lists ────────────────────────────────────────────────────────────────

class ListCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#3b82f6"


@router.get("/lists", response_model=List[ListResponse])
async def get_lists(db: AsyncSession = Depends(get_db)):
    lists = await crud.get_lists(db)
    result = []
    for lst in lists:
        count = await crud.get_list_member_count(db, lst.id)
        result.append(ListResponse(
            id=lst.id, name=lst.name, description=lst.description,
            color=lst.color, member_count=count,
            created_at=lst.created_at.isoformat() if lst.created_at else None,
        ))
    return result


@router.post("/lists", response_model=ListResponse)
async def create_list(body: ListCreate, db: AsyncSession = Depends(get_db)):
    lst = await crud.create_list(db, body.name, body.description, body.color)
    await db.commit()
    return ListResponse(id=lst.id, name=lst.name, description=lst.description,
                        color=lst.color, member_count=0,
                        created_at=lst.created_at.isoformat() if lst.created_at else None)


@router.patch("/lists/{list_id}", response_model=ListResponse)
async def update_list(list_id: int, body: ListCreate, db: AsyncSession = Depends(get_db)):
    lst = await crud.update_list(db, list_id, name=body.name,
                                  description=body.description, color=body.color)
    await db.commit()
    if not lst:
        raise HTTPException(404, "List not found")
    count = await crud.get_list_member_count(db, list_id)
    return ListResponse(id=lst.id, name=lst.name, description=lst.description,
                        color=lst.color, member_count=count,
                        created_at=lst.created_at.isoformat() if lst.created_at else None)


@router.delete("/lists/{list_id}")
async def delete_list(list_id: int, db: AsyncSession = Depends(get_db)):
    await crud.delete_list(db, list_id)
    await db.commit()
    return {"ok": True}


@router.post("/lists/{list_id}/leads")
async def add_leads_to_list(
    list_id: int,
    lead_ids: List[int] = Body(...),
    db: AsyncSession = Depends(get_db),
):
    await crud.add_to_list(db, list_id, lead_ids)
    await db.commit()
    return {"ok": True, "count": len(lead_ids)}


@router.delete("/lists/{list_id}/leads/{lead_id}")
async def remove_lead_from_list(list_id: int, lead_id: int, db: AsyncSession = Depends(get_db)):
    await crud.remove_from_list(db, list_id, lead_id)
    await db.commit()
    return {"ok": True}


# ── Saved Searches ────────────────────────────────────────────────────────────

class SavedSearchCreate(BaseModel):
    name: str
    query: str


@router.get("/saved-searches", response_model=List[SavedSearchResponse])
async def get_saved_searches(db: AsyncSession = Depends(get_db)):
    items = await crud.get_saved_searches(db)
    return [SavedSearchResponse(
        id=s.id, name=s.name, query=s.query,
        last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
        last_result_count=s.last_result_count,
        created_at=s.created_at.isoformat() if s.created_at else None,
    ) for s in items]


@router.post("/saved-searches", response_model=SavedSearchResponse)
async def create_saved_search(body: SavedSearchCreate, db: AsyncSession = Depends(get_db)):
    ss = await crud.create_saved_search(db, body.name, body.query)
    await db.commit()
    return SavedSearchResponse(id=ss.id, name=ss.name, query=ss.query,
                                last_run_at=None, last_result_count=0,
                                created_at=ss.created_at.isoformat() if ss.created_at else None)


@router.delete("/saved-searches/{ss_id}")
async def delete_saved_search(ss_id: int, db: AsyncSession = Depends(get_db)):
    await crud.delete_saved_search(db, ss_id)
    await db.commit()
    return {"ok": True}

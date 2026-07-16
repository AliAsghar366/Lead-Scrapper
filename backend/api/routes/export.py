"""Export endpoints — CSV and Excel download."""
import io
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.crud import get_all_leads_for_job, get_leads

router = APIRouter(prefix="/export", tags=["export"])

COLUMNS = [
    "Name", "Website", "Email", "Phone", "Address",
    "Category", "Facebook", "Instagram", "LinkedIn", "Twitter", "YouTube",
    "Description", "Source",
]

FIELD_MAP = {
    "Name": "name",
    "Website": "website",
    "Email": "email",
    "Phone": "phone",
    "Address": "address",
    "Category": "category",
    "Facebook": "facebook",
    "Instagram": "instagram",
    "LinkedIn": "linkedin",
    "Twitter": "twitter",
    "YouTube": "youtube",
    "Description": "description",
    "Source": "source",
}


async def _build_df(
    db: AsyncSession, job_id: Optional[int],
    has_phone: bool = False, has_email: bool = False,
    has_website: bool = False, has_address: bool = False, has_social: bool = False,
) -> pd.DataFrame:
    kwargs = dict(has_phone=has_phone, has_email=has_email, has_website=has_website,
                  has_address=has_address, has_social=has_social)
    if job_id is not None:
        leads = await get_all_leads_for_job(db, job_id, **kwargs)
    else:
        leads, _ = await get_leads(db, page=1, page_size=10000, **kwargs)
    rows = []
    for lead in leads:
        row = {col: getattr(lead, field, None) or "" for col, field in FIELD_MAP.items()}
        rows.append(row)
    return pd.DataFrame(rows, columns=COLUMNS)


@router.get("/excel")
async def export_excel(
    job_id: Optional[int] = Query(None),
    has_phone: bool = Query(False),
    has_email: bool = Query(False),
    has_website: bool = Query(False),
    has_address: bool = Query(False),
    has_social: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    df = await _build_df(db, job_id, has_phone=has_phone, has_email=has_email,
                         has_website=has_website, has_address=has_address, has_social=has_social)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
    output.seek(0)
    filtered = any([has_phone, has_email, has_website, has_address, has_social])
    suffix = "_filtered" if filtered else ""
    filename = f"leads_job{job_id}{suffix}.xlsx" if job_id else f"leads_all{suffix}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/csv")
async def export_csv(
    job_id: Optional[int] = Query(None),
    has_phone: bool = Query(False),
    has_email: bool = Query(False),
    has_website: bool = Query(False),
    has_address: bool = Query(False),
    has_social: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    df = await _build_df(db, job_id, has_phone=has_phone, has_email=has_email,
                         has_website=has_website, has_address=has_address, has_social=has_social)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    filtered = any([has_phone, has_email, has_website, has_address, has_social])
    suffix = "_filtered" if filtered else ""
    filename = f"leads_job{job_id}{suffix}.csv" if job_id else f"leads_all{suffix}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

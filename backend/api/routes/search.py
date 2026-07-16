"""Search endpoints — submit a query and track job status."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage import crud
from query_engine.parser import parse_query
from workers.job_runner import run_job

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    exclude_existing: bool = False

    @field_validator("query")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class JobStatusResponse(BaseModel):
    job_id: int
    query: str
    entity_type: str | None
    location: str | None
    status: str
    result_count: int
    error_message: str | None
    created_at: str | None
    completed_at: str | None


@router.post("", status_code=202)
async def submit_search(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a natural language search query.
    Returns a job_id immediately; processing runs in background.
    Poll GET /search/status/{job_id} to track progress.
    """
    intent = parse_query(request.query)
    job = await crud.create_job(
        db,
        query=request.query,
        entity_type=intent.entity_type,
        location=intent.location,
        keywords=intent.keywords,
    )
    await db.commit()
    background_tasks.add_task(run_job, job.id, request.exclude_existing)
    return {
        "job_id": job.id,
        "message": "Search started",
        "entity_type": intent.entity_type,
        "location": intent.location,
        "keywords": intent.keywords,
    }


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.id,
        query=job.query,
        entity_type=job.entity_type,
        location=job.location,
        status=job.status,
        result_count=job.result_count,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.post("/{job_id}/pause")
async def pause_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "running":
        raise HTTPException(400, f"Cannot pause job with status '{job.status}'")
    await crud.pause_job(db, job_id)
    return {"job_id": job_id, "status": "paused"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "paused":
        raise HTTPException(400, f"Cannot resume job with status '{job.status}'")
    await crud.resume_job(db, job_id)
    return {"job_id": job_id, "status": "running"}


@router.delete("/{job_id}")
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a single job and all its leads."""
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in ("running", "paused"):
        raise HTTPException(400, "Cannot delete a running or paused job — stop it first")
    await crud.delete_job(db, job_id)
    return {"deleted": job_id}


@router.delete("")
async def delete_all_jobs(db: AsyncSession = Depends(get_db)):
    """Wipe all jobs and all leads from the database."""
    await crud.delete_all_jobs(db)
    return {"deleted": "all"}


@router.get("/history")
async def search_history(db: AsyncSession = Depends(get_db)):
    jobs = await crud.list_jobs(db, limit=50)
    return [
        {
            "job_id": j.id,
            "query": j.query,
            "entity_type": j.entity_type,
            "location": j.location,
            "status": j.status,
            "result_count": j.result_count,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]

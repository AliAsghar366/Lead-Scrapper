"""SQLAlchemy ORM models."""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Float, Index, Integer, String, Text, UniqueConstraint,
)
from storage.database import Base


def _now():
    return datetime.now(timezone.utc)


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(512), nullable=False)
    entity_type = Column(String(256), nullable=True)
    location = Column(String(256), nullable=True)
    keywords = Column(Text, nullable=True)

    status = Column(String(32), default="pending")
    error_message = Column(Text, nullable=True)
    result_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_job_status", "status"),
        Index("ix_job_created", "created_at"),
    )


class DiscoveredUrl(Base):
    __tablename__ = "discovered_urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    domain = Column(String(512), nullable=False)
    source = Column(String(128), nullable=True)
    crawled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_disc_job_crawled", "job_id", "crawled"),
    )


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False, index=True)

    # Identity
    name = Column(String(512), nullable=True)
    category = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    industry = Column(String(256), nullable=True)
    employee_count = Column(String(64), nullable=True)
    founded_year = Column(String(16), nullable=True)
    city = Column(String(256), nullable=True)
    country = Column(String(256), nullable=True)

    # Contact
    website = Column(String(2048), nullable=True)
    email = Column(String(512), nullable=True)
    phone = Column(String(256), nullable=True)
    address = Column(Text, nullable=True)

    # Social
    facebook = Column(String(1024), nullable=True)
    instagram = Column(String(1024), nullable=True)
    linkedin = Column(String(1024), nullable=True)
    twitter = Column(String(1024), nullable=True)
    youtube = Column(String(1024), nullable=True)

    # CRM fields
    status = Column(String(32), default="new")       # new/contacted/qualified/rejected/won/lost
    score = Column(Integer, default=0)               # 0–100
    email_verified = Column(Boolean, nullable=True)  # None=unchecked, True/False

    # Meta
    source_url = Column(String(2048), nullable=True)
    source = Column(String(128), nullable=True)
    crawl_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_lead_job", "job_id"),
        Index("ix_lead_website", "website"),
        Index("ix_lead_status", "status"),
        Index("ix_lead_score", "score"),
    )


class LeadNote(Base):
    __tablename__ = "lead_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_now)


class LeadTag(Base):
    __tablename__ = "lead_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    tag = Column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("lead_id", "tag", name="uq_lead_tag"),
        Index("ix_lead_tag_tag", "tag"),
    )


class LeadList(Base):
    __tablename__ = "lead_lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(32), default="#3b82f6")
    created_at = Column(DateTime, default=_now)


class LeadListMember(Base):
    __tablename__ = "lead_list_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    list_id = Column(Integer, ForeignKey("lead_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime, default=_now)

    __table_args__ = (
        UniqueConstraint("list_id", "lead_id", name="uq_list_lead"),
    )


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    query = Column(String(512), nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    last_result_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(64), nullable=False)   # status_changed/note_added/tagged/email_verified/viewed
    detail = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=_now)

"""Read-only editions plus token-protected append-only editorial notes."""
from hashlib import sha256
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import SessionLocal
from app.models.orm import BriefPublicationNoteRow
from app.security import require_pipeline_run_token
from app.services.brief_publications import list_publications, publication

router = APIRouter(prefix="/api/v2/publications", tags=["publications"])


@router.get("")
def index(limit: int = Query(20, ge=1, le=1000), offset: int = Query(0, ge=0, le=100000)):
    return list_publications(limit, offset)


@router.get("/{slug}")
def article(slug: str):
    result = publication(slug)
    if result is None:
        raise HTTPException(status_code=404, detail="Published brief not found")
    return result


def require_editor():
    if not settings.pipeline_run_token:
        raise HTTPException(status_code=503, detail="Publication editor token is not configured")


class PublicationNote(BaseModel):
    kind: Literal["correction", "follow_up"]
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value):
        if not value.strip():
            raise ValueError("Note must contain text")
        return value.strip()


@router.post("/{slug}/notes", dependencies=[Depends(require_editor), Depends(require_pipeline_run_token)])
def append_note(slug: str, note: PublicationNote):
    edition = article(slug)
    key = sha256(f"{edition['slot_id']}\0{note.kind}\0{note.text}".encode()).hexdigest()
    with SessionLocal() as db:
        if db.get(BriefPublicationNoteRow, key) is None:
            db.add(BriefPublicationNoteRow(id=key, slot_id=edition["slot_id"], kind=note.kind, body=note.text))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                if db.get(BriefPublicationNoteRow, key) is None:
                    raise
    return article(slug)

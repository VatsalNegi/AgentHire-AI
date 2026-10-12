from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, InterviewSession, Question


def get_owned_session(
    db: Session,
    session_id: UUID,
    owner_id: UUID,
) -> InterviewSession | None:
    return db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.owner_id == owner_id,
        )
    )


def get_owned_question(
    db: Session,
    question_id: UUID,
    session_id: UUID,
    owner_id: UUID,
) -> Question | None:
    return db.scalar(
        select(Question)
        .join(InterviewSession, Question.session_id == InterviewSession.id)
        .where(
            Question.id == question_id,
            Question.session_id == session_id,
            InterviewSession.owner_id == owner_id,
        )
    )


def get_owned_document(
    db: Session,
    document_id: UUID,
    owner_id: UUID,
) -> Document | None:
    return db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == owner_id,
        )
    )

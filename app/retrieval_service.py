
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.embedding_service import embed_text
from app.models import Document, DocumentChunk


def search_documents(
    db: Session,
    query: str,
    limit: int = 5,
    document_type: str | None = None,
    owner_id: UUID | None = None,
) -> list[dict]:
    """Retrieve relevant chunks using cosine distance in pgvector."""

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")

    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20.")

    query_vector = embed_text(query.strip())
    distance = DocumentChunk.embedding.cosine_distance(query_vector)

    statement = (
        select(DocumentChunk, Document, distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.embedding.is_not(None))
        .where(Document.status == "indexed")
    )

    if document_type:
        statement = statement.where(Document.document_type == document_type)

    if owner_id is not None:
        statement = statement.where(Document.owner_id == owner_id)

    statement = statement.order_by(distance).limit(limit)
    rows = db.execute(statement).all()

    return [
        {
            "document_id": str(document.id),
            "filename": document.filename,
            "document_type": document.document_type,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "cosine_distance": float(distance_value),
        }
        for chunk, document, distance_value in rows
    ]

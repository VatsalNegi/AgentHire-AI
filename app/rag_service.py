
from sqlalchemy.orm import Session
from uuid import UUID

from app.document_service import split_text
from app.embedding_service import embed_text
from app.models import Document, DocumentChunk


def index_document(
    db: Session,
    filename: str,
    text: str,
    document_type: str = "job_description",
    owner_id: UUID | None = None,
) -> dict:
    """Store a document and its embedded text chunks in the database."""

    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty.")

    if not text or not text.strip():
        raise ValueError("Document text cannot be empty.")

    chunks = split_text(text)

    if not chunks:
        raise ValueError("No text chunks were generated.")

    try:
        document = Document(
            filename=filename.strip(),
            owner_id=owner_id,
            document_type=document_type,
            status="processing",
        )
        db.add(document)
        db.flush()

        for index, content in enumerate(chunks):
            vector = embed_text(content)

            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=content,
                embedding=vector,
                metadata_json={
                    "filename": filename.strip(),
                    "document_type": document_type,
                    "chunk_index": index,
                },
            )
            db.add(chunk)

        document.status = "indexed"
        db.commit()
        db.refresh(document)

        return {
            "document_id": str(document.id),
            "filename": document.filename,
            "document_type": document.document_type,
            "status": document.status,
            "chunks_created": len(chunks),
        }

    except Exception:
        db.rollback()
        raise

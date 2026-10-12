
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    document_type: str
    status: str
    chunks_created: int

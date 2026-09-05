"""업로드된 문서 목록 API의 응답 스키마."""

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    document_id: str
    source: str
    uploaded_at: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]

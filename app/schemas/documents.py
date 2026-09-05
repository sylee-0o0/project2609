"""업로드된 문서 목록 API의 응답 스키마."""

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    document_id: str
    source: str
    uploaded_at: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]


class ChunkDetail(BaseModel):
    chunk_id: str
    page: int
    section: str
    text: str  # 청크 원문 (섹션 제목 prefix 포함)
    embedding_preview: list[float]  # 임베딩 벡터 앞부분 일부 (전체를 다 보여주면 너무 김)
    embedding_dim: int  # 임베딩 벡터의 전체 차원 수 (bge-m3 기준 1024)


class ChunkListResponse(BaseModel):
    document_id: str
    merged_text: str  # 청크 겹침 구간을 제거하고 이어붙인, 읽기 좋은 전체 본문
    chunks: list[ChunkDetail]


class DeleteDocumentResponse(BaseModel):
    document_id: str
    deleted_chunk_count: int
    deleted_file: bool

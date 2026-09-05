"""업로드된 문서 목록 조회 API.

지금 ChromaDB에 어떤 파일들이 저장되어 있는지 확인하기 위한 용도다.
"""

from fastapi import APIRouter

from app.core import store
from app.schemas.documents import DocumentInfo, DocumentListResponse

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    """ChromaDB 동기 호출이 있으므로 `def`로 선언한다 (Starlette가 스레드풀에서 실행)."""
    docs = store.list_documents()
    return DocumentListResponse(
        documents=[
            DocumentInfo(
                document_id=d.document_id,
                source=d.source,
                uploaded_at=d.uploaded_at,
                chunk_count=d.chunk_count,
            )
            for d in docs
        ]
    )

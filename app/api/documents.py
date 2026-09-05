"""업로드된 문서 목록 조회·상세(청크)·삭제 API.

지금 ChromaDB에 어떤 파일들이 저장되어 있는지, 각 파일이 어떤 청크로 쪼개졌고
어떻게 임베딩됐는지 확인하고, 필요하면 삭제할 수 있게 한다.
"""

from fastapi import APIRouter, HTTPException

from app.core import store
from app.core.config import settings
from app.core.text_format import clean_section, clean_text, merge_overlapping_texts
from app.schemas.documents import (
    ChunkDetail,
    ChunkListResponse,
    DeleteDocumentResponse,
    DocumentInfo,
    DocumentListResponse,
)

router = APIRouter(prefix="/api", tags=["documents"])

_EMBEDDING_PREVIEW_LEN = 8  # 벡터 앞부분 몇 개만 보여줄지 (1024개를 다 보여주면 안 읽힘)


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


@router.get("/documents/{document_id}/chunks", response_model=ChunkListResponse)
def get_document_chunks(document_id: str) -> ChunkListResponse:
    """한 문서가 어떤 청크로 나뉘었고 임베딩이 어떻게 나왔는지 보여준다.

    벡터 DB 학습용 실습 프로젝트의 취지에 맞춰, 청킹 결과와 임베딩 값을
    직접 눈으로 확인할 수 있게 하는 용도다. 벡터 전체(1024차원)를 다 보내면
    응답이 너무 커지고 읽기도 어려우므로 앞부분 몇 개만 미리보기로 보낸다.
    """
    chunks = store.get_chunks(document_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="존재하지 않는 document_id입니다.")

    cleaned_texts = [clean_text(c.text) for c in chunks]

    return ChunkListResponse(
        document_id=document_id,
        # 청크를 낱개 상자로 나열하면 겹치는 구간이 중복 표시되고 문서가 조각나 보인다.
        # 겹침을 제거해 하나로 이어붙여서, 한 컨테이너 안에서 이어 읽을 수 있게 한다.
        merged_text=merge_overlapping_texts(cleaned_texts),
        chunks=[
            ChunkDetail(
                chunk_id=c.chunk_id,
                page=c.page,
                section=clean_section(c.section),
                text=cleaned,
                embedding_preview=c.embedding[:_EMBEDDING_PREVIEW_LEN],
                embedding_dim=len(c.embedding),
            )
            for c, cleaned in zip(chunks, cleaned_texts, strict=True)
        ],
    )


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(document_id: str) -> DeleteDocumentResponse:
    """문서를 ChromaDB에서 완전히 지운다. 업로드 당시 저장해둔 원본 PDF 파일도 함께 지운다."""
    deleted_count, source = store.delete_by_document_id(document_id)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="존재하지 않는 document_id입니다.")

    # 원본 파일은 `data/uploads/{job_id}_{파일명}` 형태로 저장되어 있어서 job_id를
    # 모르면 정확한 경로를 알 수 없다. 파일명으로 끝나는 파일을 찾아서 지운다.
    deleted_file = False
    for path in settings.upload_dir.glob(f"*_{source}"):
        path.unlink(missing_ok=True)
        deleted_file = True

    return DeleteDocumentResponse(
        document_id=document_id,
        deleted_chunk_count=deleted_count,
        deleted_file=deleted_file,
    )

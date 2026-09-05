"""PDF 한 건을 추출 → 청킹 → 임베딩 → 저장까지 처리하는 공통 파이프라인.

업로드 API의 백그라운드 작업(app/api/upload.py)과, 청킹/임베딩 로직이 바뀌었을 때
이미 저장된 문서를 다시 처리하는 scripts/reprocess.py 양쪽에서 재사용한다.
로직을 한 곳에만 두어야 두 경로가 서로 다르게 동작하는 걸 막을 수 있다.
"""

from collections.abc import Callable
from datetime import datetime

from app.core import embedding, store
from app.core.chunking import chunk_pages
from app.core.config import settings
from app.core.jobs import JobStatus
from app.core.pdf_extract import extract_pdf_text

ProgressCallback = Callable[[JobStatus, str], None]


def process_pdf(
    document_id: str,
    pdf_path: str,
    source: str,
    content_hash: str,
    on_progress: ProgressCallback | None = None,
) -> store.UpsertResult:
    """PDF 파일 하나를 끝까지 처리해서 ChromaDB에 저장하고 결과를 돌려준다.

    같은 파일명(source)으로 이미 저장된 청크가 있으면 먼저 지운 뒤 새로 넣는다 —
    upsert만 믿으면 새 버전의 청크 수가 이전 버전보다 적을 때 남는 청크가 그대로
    남기 때문이다 (재업로드/재처리 모두 "지우고 새로 넣는" 방식으로 통일).
    """

    def notify(status: JobStatus, message: str) -> None:
        if on_progress:
            on_progress(status, message)

    notify(JobStatus.EXTRACTING, "PDF에서 텍스트를 추출하는 중입니다.")
    pages = extract_pdf_text(pdf_path)

    notify(JobStatus.CHUNKING, "텍스트를 청크로 나누는 중입니다.")
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)

    notify(JobStatus.EMBEDDING, "청크를 벡터로 변환하는 중입니다.")
    embeddings = embedding.embed_texts([c.text for c in chunks])

    notify(JobStatus.STORING, "ChromaDB에 저장하는 중입니다.")
    store.delete_by_source(source)
    return store.upsert_chunks(
        document_id=document_id,
        source=source,
        content_hash=content_hash,
        chunks=chunks,
        embeddings=embeddings,
        uploaded_at=datetime.now(),
    )

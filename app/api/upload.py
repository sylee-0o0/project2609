"""PDF 업로드 API.

업로드 요청은 파일을 디스크에 저장하고 job_id를 즉시 반환한다. 실제 처리
(추출 → 청킹 → 임베딩 → 저장)는 BackgroundTasks로 응답 이후에 실행되며,
진행 상태는 app/core/jobs.py의 메모리 저장소에 기록된다.

## 중복 업로드 처리
- **내용이 완전히 같은 파일**(파일명이 달라도 무방)은 SHA-256 해시로 잡아낸다.
  이미 있는 내용이면 추출/청킹/임베딩을 아예 하지 않고 즉시 "이미 업로드된
  파일입니다"로 안내한다 — 같은 파일을 다시 임베딩하는 건 시간 낭비다.
- **파일명이 같은데 내용이 다른 파일**은 최신 버전으로 교체한다고 보고,
  기존 청크를 지운 뒤 새로 저장한다 (그 파일명으로는 항상 최신 버전 하나만 남는다).
"""

import hashlib
import unicodedata
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from app.core import store
from app.core.config import settings
from app.core.jobs import JobStatus, create_job, update_job
from app.core.pipeline import process_pdf
from app.schemas.upload import UploadResponse

router = APIRouter(prefix="/api", tags=["upload"])


def _process_upload(job_id: str, pdf_path: str, source: str, content_hash: str) -> None:
    """백그라운드에서 실행되는 실제 처리 파이프라인 (동기 함수).

    ChromaDB와 fastembed 호출이 모두 동기(sync) API이므로 이 함수 전체를
    동기로 유지한다. BackgroundTasks는 동기 함수를 스레드풀에서 돌려주므로
    이벤트 루프를 막지 않는다. 실제 추출/청킹/임베딩/저장 로직은
    app/core/pipeline.py에 있다 — scripts/reprocess.py와 공유하기 위해서다.
    """
    document_id = str(uuid.uuid4())
    try:
        result = process_pdf(
            document_id,
            pdf_path,
            source,
            content_hash,
            on_progress=lambda status, message: update_job(job_id, status, message),
        )
        update_job(
            job_id,
            JobStatus.DONE,
            f"완료: {result.chunk_count}개 청크를 저장했습니다.",
            chunk_count=result.chunk_count,
        )
    except Exception as exc:  # noqa: BLE001 - 실패 원인을 그대로 사용자에게 보여주기 위해 폭넓게 잡는다.
        update_job(job_id, JobStatus.FAILED, "처리 중 오류가 발생했습니다.", error=str(exc))


@router.post("/upload", response_model=UploadResponse)
def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks) -> UploadResponse:
    """PDF 파일을 업로드받아 job_id를 즉시 반환한다.

    라우트를 `async def`가 아니라 `def`로 선언했다 — 파일을 동기적으로 디스크에
    쓰는 짧은 작업이라 스레드풀에서 처리해도 무방하고, 뒤이어 실행되는 background
    task 역시 동기 파이프라인이기 때문에 함수 시그니처를 통일했다.
    """
    if file.filename is None or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")

    # 파일명은 NFC로 정규화한다 (macOS 등에서 온 NFD 파일명과 비교/검색이 어긋나는 것을 방지).
    filename = unicodedata.normalize("NFC", file.filename)

    content = file.file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    job = create_job(filename)

    # 완전히 같은 내용의 파일이 이미 있으면, 처리를 아예 시작하지 않고 바로 안내한다.
    duplicate = store.find_duplicate_by_hash(content_hash)
    if duplicate is not None:
        update_job(
            job.job_id,
            JobStatus.DUPLICATE,
            f"이미 업로드된 파일입니다 (기존 파일명: {duplicate.source}, "
            f"{duplicate.chunk_count}개 청크, 업로드 시각: {duplicate.uploaded_at}).",
        )
        return UploadResponse(job_id=job.job_id, filename=filename)

    dest_path = settings.upload_dir / f"{job.job_id}_{filename}"
    with open(dest_path, "wb") as f:
        f.write(content)

    background_tasks.add_task(_process_upload, job.job_id, str(dest_path), filename, content_hash)

    return UploadResponse(job_id=job.job_id, filename=filename)

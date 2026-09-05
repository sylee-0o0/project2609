"""작업 진행 상태 조회 API.

- `GET /api/jobs/{job_id}`: 현재 상태를 한 번 조회 (일반 REST).
- `GET /api/jobs/{job_id}/events`: SSE(Server-Sent Events)로 상태 변화를 실시간으로 흘려받는다.
  BackgroundTasks는 응답을 보낸 뒤에 실행되어 그 결과를 직접 클라이언트에 보낼 수 없으므로,
  클라이언트가 이 엔드포인트에 연결해서 app/core/jobs.py의 메모리 상태를 폴링 방식으로 받아간다.
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.jobs import JobStatus, get_job
from app.schemas.upload import JobStatusResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_POLL_INTERVAL_SECONDS = 0.5
_TERMINAL_STATUSES = {JobStatus.DONE, JobStatus.FAILED}


def _to_response(job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.job_id,
        filename=job.filename,
        status=job.status,
        message=job.message,
        error=job.error,
        chunk_count=job.chunk_count,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id입니다.")
    return _to_response(job)


@router.get("/{job_id}/events")
async def stream_job_events(job_id: str, request: Request) -> StreamingResponse:
    """job 상태를 SSE로 흘려보낸다.

    ChromaDB 등 실제 처리는 별도 스레드(BackgroundTasks)에서 동기로 실행되므로,
    이 엔드포인트는 메모리 상태를 짧은 간격으로 폴링하며 변경분만 이벤트로 내보낸다.
    상태가 DONE/FAILED에 도달하면 스트림을 닫는다.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id입니다.")

    async def event_generator():
        last_sent: tuple[str, str] | None = None
        while True:
            if await request.is_disconnected():
                break  # 클라이언트가 연결을 끊으면 폴링 루프를 즉시 종료한다.

            current = get_job(job_id)
            if current is None:
                break

            key = (current.status, current.message)
            if key != last_sent:
                payload = _to_response(current).model_dump(mode="json")
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_sent = key

            if current.status in _TERMINAL_STATUSES:
                break

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

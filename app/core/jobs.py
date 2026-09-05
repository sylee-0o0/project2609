"""업로드 처리 작업(job)의 진행 상태를 메모리에 기록한다.

## 왜 이런 구조가 필요한가
임베딩은 시간이 걸리는 작업이라 업로드 요청 안에서 동기적으로 처리하면 클라이언트가
오래 기다려야 한다. 그래서 업로드 요청은 즉시 `job_id`만 돌려주고, 실제 처리는
`BackgroundTasks`가 응답을 보낸 *뒤에* 수행한다.

문제는 `BackgroundTasks`가 응답을 이미 보낸 뒤에 실행되기 때문에, 처리 중 진행 상황을
그 응답으로는 클라이언트에 알려줄 수 없다는 점이다. 그래서:
  1. 백그라운드 작업이 진행될 때마다 이 모듈의 `JOBS` 딕셔너리에 상태를 기록하고,
  2. 클라이언트는 `GET /api/jobs/{job_id}/events` (SSE)로 연결해서 이 상태를 흘려받는다.

## 프로세스 재시작 시 사라짐
메모리 딕셔너리이므로 서버가 재시작되면 진행 중이던 job 기록은 모두 사라진다.
1-A 단계의 실습 목적상 허용하는 단순화이며, 필요해지면 (2차 이후) DB 테이블로
옮기는 것을 재논의한다.
"""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"  # PDF → 텍스트 추출 중
    CHUNKING = "chunking"  # 텍스트 → 청크 분할 중
    EMBEDDING = "embedding"  # 청크 → 벡터 변환 중
    STORING = "storing"  # ChromaDB 저장 중
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    filename: str
    status: JobStatus = JobStatus.PENDING
    message: str = ""
    error: str | None = None
    chunk_count: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


_lock = threading.Lock()
JOBS: dict[str, Job] = {}


def create_job(filename: str) -> Job:
    job = Job(job_id=str(uuid.uuid4()), filename=filename)
    with _lock:
        JOBS[job.job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        return JOBS.get(job_id)


def update_job(
    job_id: str,
    status: JobStatus,
    message: str = "",
    error: str | None = None,
    chunk_count: int | None = None,
) -> None:
    """백그라운드 작업 스레드에서 호출된다.

    FastAPI의 BackgroundTasks는 동기 함수를 스레드풀에서 실행하므로, 이 함수는
    요청을 처리하는 asyncio 이벤트 루프와 다른 스레드에서 호출될 수 있다.
    그래서 딕셔너리 접근을 threading.Lock으로 보호한다 (asyncio.Lock이 아님에 주의).
    """
    with _lock:
        job = JOBS.get(job_id)
        if job is None:
            return
        job.status = status
        job.message = message
        job.updated_at = datetime.now()
        if error is not None:
            job.error = error
        if chunk_count is not None:
            job.chunk_count = chunk_count

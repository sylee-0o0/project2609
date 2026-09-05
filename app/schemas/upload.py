"""업로드/작업 상태 API의 요청·응답 스키마."""

from datetime import datetime

from pydantic import BaseModel

from app.core.jobs import JobStatus


class UploadResponse(BaseModel):
    job_id: str
    filename: str


class JobStatusResponse(BaseModel):
    job_id: str
    filename: str
    status: JobStatus
    message: str
    error: str | None = None
    chunk_count: int | None = None
    updated_at: datetime

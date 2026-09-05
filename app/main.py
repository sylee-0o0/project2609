"""FastAPI 애플리케이션 엔트리포인트.

개발 중 CORS는 Vite 프록시(frontend/vite.config.js)로 해결하므로
여기에 CORS 미들웨어를 추가하지 않는다 (CLAUDE.md).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import jobs, upload
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    yield


app = FastAPI(title="글로벌 ICT 동향 리포트 조회", lifespan=lifespan)

app.include_router(upload.router)
app.include_router(jobs.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """서버가 떠 있는지 확인하는 용도. 프론트엔드 개발 시 프록시 연결 확인에도 쓴다."""
    return {"status": "ok"}

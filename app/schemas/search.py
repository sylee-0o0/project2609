"""검색 API의 요청·응답 스키마."""

from pydantic import BaseModel


class SearchResult(BaseModel):
    document_id: str
    chunk_id: str
    source: str  # 파일명 — 모든 결과에 출처를 붙인다 (CLAUDE.md)
    page: int
    section: str
    text: str
    distance: float  # 작을수록 유사 (코사인 거리)
    similarity: float  # 1 - distance. 사람이 보기엔 이쪽이 직관적이라 함께 내려준다.


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    message: str | None = None  # 관련 문서가 없을 때 사용자에게 보여줄 안내 문구

"""의미 기반 검색 API (1-B).

질문(자연어)을 받아 임베딩한 뒤, ChromaDB에서 코사인 거리가 가장 가까운 청크
top_k개를 찾아 돌려준다. 모든 결과에는 출처(파일명·페이지·섹션)를 반드시 붙인다 —
CLAUDE.md: "출처 없는 결과는 실패로 본다."
"""

from fastapi import APIRouter, Query

from app.core import embedding, store
from app.core.config import settings
from app.schemas.search import SearchResponse, SearchResult

router = APIRouter(prefix="/api", tags=["search"])

_NO_RESULT_MESSAGE = "관련 문서를 찾을 수 없습니다."
_MAX_TOP_K = 20


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="검색할 질문(자연어)"),
    top_k: int = Query(5, ge=1, le=_MAX_TOP_K, description="가져올 결과 개수"),
) -> SearchResponse:
    """라우트를 `async def`가 아니라 `def`로 선언했다.

    임베딩 계산(fastembed)과 ChromaDB 조회가 모두 동기 API라서, `def`로 선언하면
    Starlette이 자동으로 스레드풀에서 실행해줘 이벤트 루프를 막지 않는다.
    """
    query_vector = embedding.embed_texts([q])[0]
    matches = store.query_similar(query_vector, top_k=top_k)

    if not matches:
        return SearchResponse(query=q, results=[], message=_NO_RESULT_MESSAGE)

    # distance는 작을수록 유사하다 (score/유사도와는 방향이 반대).
    # 최상위(가장 가까운) 결과의 distance가 임계값을 넘으면, 상위 결과라 해도
    # 실제로는 관련성이 낮다고 보고 "찾을 수 없습니다"로 응답한다.
    top_distance = matches[0].distance
    if top_distance > settings.search_distance_threshold:
        return SearchResponse(query=q, results=[], message=_NO_RESULT_MESSAGE)

    results = [
        SearchResult(
            document_id=m.document_id,
            chunk_id=m.chunk_id,
            source=m.source,
            page=m.page,
            section=m.section,
            text=m.text,
            distance=m.distance,
            similarity=1.0 - m.distance,  # ChromaDB 코사인 거리 = 1 - 코사인 유사도
        )
        for m in matches
    ]
    return SearchResponse(query=q, results=results)

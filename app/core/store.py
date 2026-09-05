"""ChromaDB 접근 계층.

## 이 파일만 chromadb를 import 하는 이유
CLAUDE.md 2차 계획은 ChromaDB → PostgreSQL + pgvector 교체다. 벡터 DB 관련 호출을
이 파일 하나로 모아두면, 나중에 교체할 때 이 파일의 내부 구현만 바꾸면 되고
나머지 코드(app/api 등)는 `get_collection()` / `upsert_chunks()` 같은 함수 시그니처만
알면 되므로 영향받지 않는다.

## 동기 API 주의
ChromaDB의 PersistentClient는 동기(sync) API다. FastAPI 라우트를 `async def`로 선언한 뒤
이 모듈 함수를 직접 호출하면 이벤트 루프가 그 작업이 끝날 때까지 완전히 멈춰서
다른 요청을 전혀 처리하지 못한다. 그래서:
  - 이 모듈은 항상 동기 함수로 유지한다.
  - 호출하는 쪽(app/api)에서 `def` 라우트로 선언하거나
    `starlette.concurrency.run_in_threadpool()`로 감싸서 스레드풀에서 실행한다.

## 거리 척도(distance metric) 고정
컬렉션 생성 시 `metadata={"hnsw:space": "cosine"}`으로 코사인 거리를 지정한다.
이 값은 컬렉션 생성 시점에 한 번 정해지면 나중에 바꿀 수 없다 (바꾸려면 컬렉션을
새로 만들고 전체 재적재해야 한다). distance는 0에 가까울수록 유사하고, 1-B에서
쓰는 "score"(유사도)와는 방향이 반대라는 점을 검색 코드에서 항상 유의해야 한다.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.chunking import Chunk
from app.core.config import settings

_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    """PersistentClient를 지연 생성해서 재사용한다 (여러 번 만들 필요 없음)."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    return _client


def get_collection() -> Collection:
    """컬렉션을 가져오거나, 없으면 코사인 거리로 새로 만든다."""
    client = get_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )


@dataclass
class UpsertResult:
    document_id: str
    chunk_count: int


def upsert_chunks(
    document_id: str,
    source: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    uploaded_at: datetime | None = None,
) -> UpsertResult:
    """청크와 임베딩을 ChromaDB에 저장한다.

    재업로드 시 같은 document_id로 다시 들어올 수 있으므로 `add`가 아니라
    `upsert`를 쓴다 — 같은 id가 이미 있으면 덮어쓰고, 없으면 새로 추가한다.

    필수 메타데이터(CLAUDE.md): document_id / chunk_id / source / page / section / uploaded_at
    이 중 하나라도 빠지면 나중에 출처를 못 붙이거나 재적재가 필요해지므로 절대 누락하지 않는다.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"청크 수({len(chunks)})와 임베딩 수({len(embeddings)})가 일치하지 않습니다."
        )

    uploaded_at = uploaded_at or datetime.now()
    uploaded_at_iso = uploaded_at.isoformat()

    ids: list[str] = []
    metadatas: list[dict[str, Any]] = []
    documents: list[str] = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{document_id}::{i}"
        ids.append(chunk_id)
        documents.append(chunk.text)
        metadatas.append(
            {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "source": source,
                "page": chunk.page,
                "section": chunk.section,
                "uploaded_at": uploaded_at_iso,
            }
        )

    collection = get_collection()
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    return UpsertResult(document_id=document_id, chunk_count=len(chunks))


@dataclass
class QueryMatch:
    document_id: str
    chunk_id: str
    source: str
    page: int
    section: str
    text: str
    distance: float


def query_similar(query_embedding: list[float], top_k: int) -> list[QueryMatch]:
    """쿼리 벡터와 가장 가까운(코사인 거리가 작은) 청크 top_k개를 찾는다.

    컬렉션이 비어 있으면 빈 리스트를 반환한다 — 호출하는 쪽(app/api/search.py)이
    "관련 문서 없음"과 "아직 업로드된 문서가 없음"을 구분해서 처리한다.
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    # collection.query()는 여러 쿼리를 한 번에 처리할 수 있게 설계되어 있어서
    # 결과가 "쿼리별 리스트의 리스트"로 온다. 우리는 쿼리를 하나만 보냈으므로 [0]만 쓴다.
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    matches: list[QueryMatch] = []
    for doc, meta, dist in zip(documents, metadatas, distances, strict=True):
        matches.append(
            QueryMatch(
                document_id=meta["document_id"],
                chunk_id=meta["chunk_id"],
                source=meta["source"],
                page=meta["page"],
                section=meta["section"],
                text=doc,
                distance=dist,
            )
        )
    return matches

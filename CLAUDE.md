# 글로벌 ICT 동향 리포트 조회

한국어 PDF를 업로드해 의미 기반으로 검색하는 웹 앱. **벡터 DB 학습용 실습 프로젝트.**

## 현재 단계

| | 목표 | 상태 |
|---|---|---|
| **1-A** | PDF 업로드 → 텍스트 추출 → 청킹 → 임베딩 → ChromaDB 저장 | **진행** |
| 1-B | 웹 UI에서 유사도 검색 (질문 → top_k + 출처) | 예정 |
| 1-C | 키워드 검색 추가 + 하이브리드 결합 | 예정 |
| 2차 | ChromaDB → PostgreSQL + pgvector 교체 | 예정 |

**지시받지 않은 단계를 미리 만들지 않는다.** 1-A 중에 검색 UI를 만들거나, 1차에서 pgvector를 쓰지 않는다.
단계마다 동작을 확인하고 넘어가는 것이 이 프로젝트의 목적이다.

---

## 기술 스택
모든 설치는 프로젝트 폴더내에 격리한다. 격리가 안되는 상황이 발생하면 진행을 중지하고 대안을 준비해서 사용자에게 질문한다.


| 영역 | 선택 |
|---|---|
| Python | **3.12** (`.python-version` 고정) |
| 패키지 | **uv** — `uv add`, `uv run`. `pip` 금지 |
| Backend | FastAPI / Uvicorn, pydantic-settings(`.env`), ruff |
| PDF 추출 | **pypdf** (BSD). pymupdf는 AGPL이라 제외 |
| 청킹 | langchain-text-splitters `RecursiveCharacterTextSplitter` |
| 업로드 | python-multipart |
| Vector DB | **ChromaDB** `PersistentClient` (로컬 영속화) |
| 임베딩 | **fastembed** + `BAAI/bge-m3` (1024차원, 접두사 불필요) |
| Frontend | **React 18 + Vite + Tailwind**, JavaScript |

* Node/React: npm install로 node_modules/에 격리한다. npm install -g를 사용하지 않는다 
 - 런타임 버전: mise로 고정한다 (.mise.toml에 Python·Node 버전 명시) 


- Chroma 기본 모델 `all-MiniLM-L6-v2`는 **영어 전용이라 사용 금지.**
- `BAAI/bge-m3`를 fastembed가 지원하지 않으면 **진행을 멈추고 재논의한다.** 임의로 다른 모델을 고르지 않는다.
  ```python
  from fastembed import TextEmbedding

  print([m["model"] for m in TextEmbedding.list_supported_models()])
  ```
- 모델은 첫 실행 시 다운로드된다(약 2GB). 캐시 경로를 `.env`로 지정하고 `.gitignore`에 넣는다.
- 상태 관리·데이터 페칭·UI 킷 라이브러리는 쓰지 않는다. `useState`로 충분하다.

---

## 구현 규칙

### 비동기

- **ChromaDB는 동기 API다.** `async def`에서 직접 호출하면 이벤트 루프가 멈춘다.
  → 라우트를 `def`로 선언하거나 `run_in_threadpool()`로 감싼다.
- **임베딩은 `BackgroundTasks`로 처리한다.** 업로드 응답은 즉시 `job_id`를 돌려준다.
- `BackgroundTasks`는 응답을 보낸 뒤 실행되므로 클라이언트에 직접 못 보낸다.
  → 진행 상태를 `dict[job_id]` 메모리 저장소에 기록하고, SSE(`GET /api/jobs/{job_id}/events`)가 그걸 읽어 흘려보낸다.
  → 프로세스 재시작 시 사라진다. 

### 한국어 처리 — 가장 큰 함정
- **PowerPoint로 만든 PDF는 pypdf 기본 추출에서 띄어쓰기가 사라진다** (`오픈뱅킹데이터이동성을활용해`).
  → `extract_text(extraction_mode="layout")`와 기본 모드를 **둘 다 시도**하고, `한글 어절 수 / 한글 글자 수` 비율이 높은 쪽을 쓴다.
  → **추출 직후 텍스트를 눈으로 확인하는 단계를 넣는다.** 여기서 안 잡으면 원인을 못 찾는다.
- 파일명은 `unicodedata.normalize("NFC", name)`으로 정규화. 파일 입출력은 `encoding="utf-8"` 명시.

### 데이터
- 청킹 기준선: **600자 / overlap 100자**. 각 청크 앞에 상위 제목을 prefix로 붙인다.
  기준선이다. 검색이 이상하면 가장 먼저 조정
- **메타데이터를 누락하지 않는다.** 빠뜨리면 전체 재적재가 필요하다.
  `document_id` / `chunk_id` / `source` / `page` / `section` / `uploaded_at`
- 거리 척도는 컬렉션 생성 시 고정된다: `metadata={"hnsw:space": "cosine"}`. 나중에 못 바꾼다.
- 재업로드가 가능하므로 `add`가 아니라 **`upsert`**를 쓴다.
- **`core/store.py`만 `chromadb`를 import한다.** 2차에서 이 파일 하나만 교체하면 되도록 유지하

### 검색 (1-B)
- **모든 결과에 출처를 붙인다** (파일명 · 페이지 · 섹션). 출처 없는 결과는 실패로 본다.
- **distance는 작을수록 유사하다.** score와 방향이 반대다.
- 최상위 distance가 임계값을 넘으면 "관련 문서를 찾을 수 없습니다"로 응답한다. 임계값은 `.env`로 뺀다.

---

## 명령

```bash
# Backend (루트)
uv sync
uv run uvicorn app.main:app --reload      # :8000

# Frontend (frontend/)
npm install && npm run dev                # :5173, /api → :8000 프록시
```

브라우저는 `:5173`으로 접속. 개발 중 CORS는 **Vite 프록시**로 해결 — 백엔드에 CORS 미들웨어를 넣지 않는다.

---

## 작업 방식

- **모든 설명·주석·UI 문구는 한국어로.**
- 벡터 DB를 첫시간에 읽는 문서이니 새로운 개념(임베딩, 청킹, 거리 척도 등)이 나오면 주석에 설명을 추가 한다
- 예외 처리를 철저하게 한다.
- 라이브러리 API가 불확실하면 **추측하지 말고 확인한다.** 특히 fastembed 모델명과 ChromaDB `where` 문법은 버전마다 다르다.
- 서버는 scripts/dev.sh 를 생성해서  start,stop,status를 통해 관리를 용이하게 한다, 서버 기동시 접근 port를 표시한다.

## 하지 말 것
- `pip install` (→ `uv add`) / JS 의존성에 `uv add`
- Chroma 기본 임베딩 모델 사용
- `async def` 안에서 ChromaDB 동기 호출
- 업로드 요청 안에서 임베딩 동기 처리
- 메타데이터 없이 청크 저장 / 출처 없이 결과 반환
- 상태 관리·데이터 페칭·UI 킷 라이브러리 도입
- 백엔드에 CORS 미들웨어 추가
- `EventSource` cleanup 누락 → StrictMode 비활성화로 해결하기
- 지시받지 않은 단계 선행 구현 (특히 1차 중 pgvector)

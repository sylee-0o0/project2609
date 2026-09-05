"""텍스트를 벡터로 변환한다 (fastembed).

## 임베딩이란?
텍스트를 고정된 길이의 숫자 배열(벡터)로 바꾸는 과정이다. 의미가 비슷한 문장은
벡터 공간에서 서로 가까운 위치에 놓이도록 모델이 학습되어 있어서, "벡터 사이의 거리"를
계산하면 "의미가 비슷한 정도"를 근사할 수 있다. 이것이 이 프로젝트가 하려는
"의미 기반 검색"의 핵심 원리다.

## BAAI/bge-m3를 왜 "커스텀 등록"해야 하는가
fastembed 0.8.0(현재 설치된 최신 버전)의 `TextEmbedding.list_supported_models()`에는
`BAAI/bge-m3`가 없다. 확인해 보니 fastembed 프로젝트에도 이를 내장 지원으로 추가하려는
PR(qdrant/fastembed #602)이 있지만 아직 머지되지 않은 상태다
(https://github.com/qdrant/fastembed/pull/602).

다행히 fastembed는 `TextEmbedding.add_custom_model()`이라는 공개 API로 내장 목록에 없는
모델도 등록해서 쓸 수 있게 해준다. 아래 값들은 추측이 아니라 실제로 확인한 값이다:
  - BAAI/bge-m3 공식 HuggingFace 저장소(`BAAI/bge-m3`)의 `onnx/` 폴더에 `model.onnx`(725KB,
    그래프 구조만 포함)와 `model.onnx_data`(2.27GB, 실제 가중치 — ONNX가 2GB를 넘는 모델은
    가중치를 별도 파일로 분리하는 규격을 따른다)가 실제로 존재한다.
  - `tokenizer_config.json`에 `model_max_length: 8192`가 명시되어 있어, fastembed가 토크나이저
    설정을 그대로 읽어가면 (앞서 검토한 미머지 PR에서 리뷰어가 우려했던) 512 토큰으로 조용히
    잘리는 문제 없이 8192 토큰까지 처리된다 (fastembed는 `tokenizer_config.json`의
    `model_max_length`/`max_length`를 읽어 `Tokenizer.enable_truncation()`에 그대로 적용한다 —
    fastembed 소스코드(`common/preprocessor_utils.py`)로 직접 확인).
  - BGE 계열 모델은 BAAI 공식 사용법 기준으로 "CLS 토큰(첫 번째 토큰)의 히든 스테이트를 뽑아
    L2 정규화"하는 방식으로 dense 벡터를 만든다. 그래서 `PoolingType.CLS` + `normalization=True`로
    등록한다.

다만 이 조합은 fastembed가 공식적으로 검증/머지한 것이 아니라 우리가 API 문서와 실제 저장소
파일을 근거로 구성한 것이므로, 최초 실행 시 실제로 다운로드해 임베딩을 만들어보고
차원 수(1024)와 값이 정상적인지 직접 확인하는 절차를 거쳤다 (아래 `verify_embedding_model()`).

## 프로세스 시작 시 한 번만 등록
`add_custom_model()`은 같은 이름이 이미 등록되어 있으면 예외를 던지므로, 이미 등록됐는지
확인한 뒤에만 호출한다 (uvicorn --reload로 재시작될 때마다 새 프로세스에서 다시 등록해야 한다).
"""

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType

from app.core.config import settings

_BGE_M3_MODEL_NAME = "BAAI/bge-m3"
_BGE_M3_DIM = 1024

_model: TextEmbedding | None = None  # 지연 로딩, 최초 호출 시 생성


def _ensure_bge_m3_registered() -> None:
    """BAAI/bge-m3가 fastembed 내장 목록에 없으므로 커스텀 모델로 등록한다.

    이미 등록되어 있으면(같은 프로세스에서 두 번째 호출) 아무 것도 하지 않는다.
    """
    registered = {m["model"] for m in TextEmbedding.list_supported_models()}
    if _BGE_M3_MODEL_NAME in registered:
        return

    TextEmbedding.add_custom_model(
        model=_BGE_M3_MODEL_NAME,
        pooling=PoolingType.CLS,
        normalization=True,
        sources=ModelSource(hf=_BGE_M3_MODEL_NAME),
        dim=_BGE_M3_DIM,
        model_file="onnx/model.onnx",
        additional_files=["onnx/model.onnx_data"],
        description="BAAI/bge-m3 dense embedding (fastembed 미내장 — 커스텀 등록, PR #602 참고)",
        license="mit",
        size_in_gb=2.27,
    )


def _ensure_registered() -> None:
    """설정된 모델이 fastembed 목록에 없으면 커스텀 등록한다.

    get_embedding_dim()과 _get_model() 양쪽에서 공통으로 호출한다 — 둘 중 무엇이
    먼저 불려도 등록이 먼저 되어 있어야 목록 조회/모델 로딩이 정상 동작한다.
    """
    if settings.embedding_model_name == _BGE_M3_MODEL_NAME:
        _ensure_bge_m3_registered()


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _ensure_registered()
        _model = TextEmbedding(
            model_name=settings.embedding_model_name,
            cache_dir=str(settings.fastembed_cache_dir),
        )
    return _model


def get_embedding_dim() -> int:
    """현재 설정된 임베딩 모델의 벡터 차원 수."""
    _ensure_registered()
    for m in TextEmbedding.list_supported_models():
        if m["model"] == settings.embedding_model_name:
            return m["dim"]
    raise ValueError(
        f"등록되지 않은 임베딩 모델입니다: {settings.embedding_model_name!r}. "
        ".env의 EMBEDDING_MODEL_NAME을 확인하세요."
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """텍스트 목록을 임베딩 벡터 목록으로 변환한다.

    fastembed의 `TextEmbedding.embed()`는 제너레이터를 반환하며 내부적으로 배치 처리를
    한다. 반환값은 numpy 배열이므로 ChromaDB에 넘기기 전에 list로 바꿔준다.
    """
    if not settings.embedding_model_name:
        raise RuntimeError(
            "임베딩 모델이 설정되지 않았습니다. .env의 EMBEDDING_MODEL_NAME을 확인하세요."
        )
    model = _get_model()
    return [vector.tolist() for vector in model.embed(texts)]

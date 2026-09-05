"""텍스트를 벡터로 변환한다 (fastembed).

## 임베딩이란?
텍스트를 고정된 길이의 숫자 배열(벡터)로 바꾸는 과정이다. 의미가 비슷한 문장은
벡터 공간에서 서로 가까운 위치에 놓이도록 모델이 학습되어 있어서, "벡터 사이의 거리"를
계산하면 "의미가 비슷한 정도"를 근사할 수 있다. 이것이 이 프로젝트가 하려는
"의미 기반 검색"의 핵심 원리다.

## ⚠️ 현재 상태: 모델 미확정
CLAUDE.md는 `BAAI/bge-m3`(1024차원)를 지정했지만, fastembed 0.8.0(현재 설치된 최신 버전)의
`TextEmbedding.list_supported_models()`를 확인한 결과 지원 목록에 없다.
CLAUDE.md 규칙("지원하지 않으면 진행을 멈추고 재논의한다. 임의로 다른 모델을 고르지 않는다")에
따라, 이 모듈은 실제 임베딩 호출을 아직 구현하지 않고 골격만 잡아둔다.
`.env`의 EMBEDDING_MODEL_NAME이 채워지고 이 파일의 TODO가 해소되기 전까지
`embed_texts()`는 명확한 에러를 던진다.
"""

from app.core.config import settings

_model = None  # fastembed.TextEmbedding 인스턴스 (지연 로딩, 최초 호출 시 생성)


def get_embedding_dim() -> int:
    """현재 설정된 임베딩 모델의 벡터 차원 수.

    TODO(모델 확정 후): fastembed 모델 목록의 dim 값으로 채운다.
    """
    raise NotImplementedError(
        "임베딩 모델이 아직 확정되지 않았습니다. "
        "BAAI/bge-m3가 fastembed에서 지원되지 않아 대체 모델을 재논의해야 합니다. "
        "app/core/embedding.py와 .env의 EMBEDDING_MODEL_NAME을 확인하세요."
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """텍스트 목록을 임베딩 벡터 목록으로 변환한다.

    TODO(모델 확정 후):
        from fastembed import TextEmbedding
        global _model
        if _model is None:
            _model = TextEmbedding(
                model_name=settings.embedding_model_name,
                cache_dir=str(settings.fastembed_cache_dir),
            )
        return [v.tolist() for v in _model.embed(texts)]
    """
    if not settings.embedding_model_name:
        raise NotImplementedError(
            "임베딩 모델이 아직 확정되지 않았습니다 (.env의 EMBEDDING_MODEL_NAME이 비어 있음). "
            "BAAI/bge-m3가 fastembed에서 지원되지 않는 것을 확인했으므로, "
            "대체 모델을 사용자와 재논의한 뒤 이 함수를 완성해야 합니다."
        )
    raise NotImplementedError("모델은 확정되었지만 embed_texts() 구현이 아직 연결되지 않았습니다.")

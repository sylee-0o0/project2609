"""애플리케이션 설정.

pydantic-settings의 BaseSettings를 쓰면 .env 파일과 환경 변수를 자동으로
읽어서 타입 검증까지 해준다. 코드 어디서든 `from app.core.config import settings`로
가져다 쓰면 되고, 값을 하드코딩하지 않는 것이 목적이다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ChromaDB
    chroma_persist_dir: Path = Path("./data/chroma")
    chroma_collection_name: str = "ict_reports"

    # 업로드
    upload_dir: Path = Path("./data/uploads")

    # 임베딩 (fastembed)
    # BAAI/bge-m3(1024차원)는 fastembed 0.8.0에 내장되어 있지 않아
    # app/core/embedding.py에서 add_custom_model()로 커스텀 등록한다.
    # 근거(추측 아님): BAAI/bge-m3 공식 HF 저장소에 onnx/model.onnx + onnx/model.onnx_data가
    # 실제로 존재하고, tokenizer_config.json에 model_max_length=8192가 명시되어 있음을 확인함.
    embedding_model_name: str = "BAAI/bge-m3"
    fastembed_cache_dir: Path = Path("./.fastembed_cache")

    # 청킹 기준선 (CLAUDE.md: 600자 / overlap 100자)
    chunk_size: int = 600
    chunk_overlap: int = 100

    # 검색 (1-B에서 사용)
    # ⚠️ 짧은 키워드 질문의 한계: 자연어 질문("~는 왜 중요한가?")은 관련/무관 질문의
    # distance가 뚜렷하게 갈리지만(0.2~0.3 vs 0.5~0.6), 단어 하나짜리 질문("규제",
    # "PayPal", "JP모건" 등)은 실제로 문서에 있는 단어인데도 distance가 0.41~0.56까지
    # 올라가서, 완전히 무관한 질문(0.55~0.57)과 구간이 겹친다. 즉 순수 임베딩 거리만으로는
    # 둘을 항상 깔끔하게 가르는 임계값이 없다 — 이건 dense 임베딩만 쓰는 1-B의 근본적인
    # 한계이고, CLAUDE.md가 1-C에서 키워드(BM25) 검색을 하이브리드로 더하려는 이유이기도 하다.
    # 그때까지는 "있는데 안 나오는" 실패가 "없는데 나오는" 실패보다 더 나쁘다고 보고,
    # 짧은 키워드 질문도 웬만하면 통과하도록 느슨하게(0.6) 잡았다.
    search_distance_threshold: float = 0.6

    def ensure_dirs(self) -> None:
        """앱 시작 시 필요한 로컬 디렉터리를 만들어 둔다."""
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.fastembed_cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """설정 객체를 한 번만 생성해서 재사용한다 (lru_cache)."""
    return Settings()


settings = get_settings()

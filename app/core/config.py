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
    search_distance_threshold: float = 0.8

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

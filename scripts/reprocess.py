"""이미 업로드된 모든 문서를 최신 청킹/임베딩 로직으로 다시 처리한다.

청킹 알고리즘이나 임베딩 모델이 바뀌었을 때, 원본 PDF가 data/uploads/에 그대로
남아있는 것을 이용해 재추출 → 재청킹 → 재임베딩 → 재저장한다. 업로드 API와 같은
파이프라인(app/core/pipeline.py)을 그대로 재사용하므로 결과가 새로 업로드한 것과
동일하다.

사용법:
    uv run python scripts/reprocess.py            # 전체 재처리
    uv run python scripts/reprocess.py --dry-run   # 대상 목록만 확인, 실제 처리는 안 함
"""

import argparse
import hashlib
import sys
import unicodedata
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.pipeline import process_pdf  # noqa: E402


def _parse_source_from_filename(path: Path) -> str:
    """`{job_id}_{원본파일명}.pdf` 형식에서 원본 파일명만 뽑아낸다."""
    # job_id는 UUID(36자) + "_" 이므로 그 뒤가 전부 원본 파일명이다.
    name = path.name
    return unicodedata.normalize("NFC", name[37:] if len(name) > 37 and name[36] == "_" else name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="대상만 출력, 실제 처리는 안 함")
    args = parser.parse_args()

    pdf_paths = sorted(settings.upload_dir.glob("*.pdf"))
    if not pdf_paths:
        print("data/uploads/에 재처리할 PDF가 없습니다.")
        return

    print(f"총 {len(pdf_paths)}개 파일을 재처리합니다.\n")

    for i, path in enumerate(pdf_paths, start=1):
        source = _parse_source_from_filename(path)
        print(f"[{i}/{len(pdf_paths)}] {source}")

        if args.dry_run:
            continue

        content = path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        # 업로드 API와 동일하게 깨끗한 UUID를 쓴다 — 파일명을 그대로 쓰면 공백·한글이
        # 섞여 document_id로 URL 경로에 넣을 때 문제가 생긴다.
        document_id = str(uuid.uuid4())

        try:
            result = process_pdf(
                document_id,
                str(path),
                source,
                content_hash,
                on_progress=lambda status, message: print(f"    - {status.value}: {message}"),
            )
            print(f"    -> 완료: {result.chunk_count}개 청크")
        except Exception as exc:  # noqa: BLE001 - 스크립트 실행 중 하나가 실패해도 나머지는 계속 처리
            print(f"    -> 실패: {exc}")

    print("\n재처리 완료.")


if __name__ == "__main__":
    main()

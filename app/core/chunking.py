"""추출된 페이지 텍스트를 검색용 청크로 나눈다.

## 청킹 기준선 (CLAUDE.md)
- 600자 / overlap 100자를 기준선으로 삼는다. 검색 결과가 이상하면 가장 먼저 조정할 값이다.
- 각 청크 앞에 "상위 제목"(section)을 prefix로 붙인다. 임베딩 모델이 청크만 보고는
  문맥(어느 챕터/섹션인지)을 모르기 때문에, 제목을 붙여주면 검색 품질이 올라간다.

## 왜 RecursiveCharacterTextSplitter인가
단순히 N자마다 자르면 문장이 중간에 끊겨 의미가 훼손된다. RecursiveCharacterTextSplitter는
문단(\n\n) → 줄바꿈(\n) → 문장 부호 → 글자 순으로 "더 큰 단위"부터 나눠보려고 시도해서,
가능한 한 의미 단위를 보존하면서 목표 길이(chunk_size)에 맞춘다. overlap은 청크 경계에서
문맥이 잘려도 앞 청크의 꼬리가 다음 청크 앞에 다시 나오게 해서 손실을 줄인다.
"""

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.pdf_extract import PageText

# 섹션(상위 제목) 후보로 볼 수 있는 줄의 패턴.
# 완벽한 규칙은 없어서 최대한 보수적으로 잡는다 — 오탐이 나면 이전 섹션 이름이 계속 이어질 뿐이라
# 청크 텍스트 자체는 잃지 않는다. 다만 이 휴리스틱은 "추출 직후 눈으로 확인" 단계에서
# 함께 검증해야 한다.
_HEADING_RE = re.compile(
    r"^(?:[Ⅰ-Ⅹ0-9１-９]{1,3}[.\)]|제?\s*[0-9]+\s*[장절]|[가-힣]\.)\s*\S"
)
_MAX_HEADING_LEN = 40


@dataclass
class Chunk:
    page: int
    section: str
    text: str  # section prefix가 포함된 최종 텍스트 (임베딩에 그대로 사용)


def _detect_heading(line: str) -> str | None:
    """한 줄이 제목처럼 보이면 그 줄을 반환하고, 아니면 None."""
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_LEN:
        return None
    if stripped.endswith((".", ",", "다", "요")):
        # 문장으로 끝나는 줄은 본문일 가능성이 높다 (단, "다/요"로 끝나는 제목도 있어
        # 완벽하지 않다 — 오탐 시 이전 섹션명이 유지되므로 치명적이지 않다).
        return None
    if _HEADING_RE.match(stripped):
        return stripped
    return None


def chunk_pages(
    pages: list[PageText],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """여러 페이지의 텍스트를 순서대로 훑으며 섹션을 추적하고, 페이지 단위로 청킹한다.

    페이지 경계를 넘어 청크를 합치지 않는다 — 청크마다 정확한 page 메타데이터를
    붙여야 하기 때문이다 (CLAUDE.md: 메타데이터 누락 금지).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    current_section = ""  # 제목 미발견 상태 — 빈 문자열로 둔다 (화면에 "제목 없음" 노출 방지)

    for page in pages:
        for line in page.text.splitlines():
            heading = _detect_heading(line)
            if heading:
                current_section = heading
                break  # 페이지당 한 번만 갱신 — 페이지 첫머리 제목을 기대

        for piece in splitter.split_text(page.text):
            # 제목을 찾은 경우에만 prefix를 붙인다. 제목이 없는데도 "[] "를 붙이면
            # 모든 청크 앞에 의미 없는 토큰만 추가되어 임베딩에 잡음이 될 뿐이다.
            prefixed = f"[{current_section}] {piece}" if current_section else piece
            chunks.append(Chunk(page=page.page, section=current_section, text=prefixed))

    return chunks

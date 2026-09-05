"""추출된 페이지 텍스트를 검색용 청크로 나눈다.

## 청킹 기준선 (CLAUDE.md)
- 600자 / overlap 100자를 기준선으로 삼는다. 검색 결과가 이상하면 가장 먼저 조정할 값이다.
- 각 청크 앞에 "상위 제목"(section)을 prefix로 붙인다. 임베딩 모델이 청크만 보고는
  문맥(어느 챕터/섹션인지)을 모르기 때문에, 제목을 붙여주면 검색 품질이 올라간다.

## 왜 "의미 단위" 기반으로 다시 짰는가
처음 버전은 페이지 텍스트 전체를 RecursiveCharacterTextSplitter에 그대로 넘겼다.
이 방식의 문제: 리포트의 글머리 기호(•, ○, ➢) 항목 하나가 줄바꿈 없이 600자를
넘기는 경우, 문단(\n\n)도 줄바꿈(\n)도 마침표+공백(". ")도 없어서 splitter가
마지막 수단인 "공백" 기준으로 아무 데서나 잘라버린다 — 그 결과
"핵심 기준이 '어떤 | 표준을 충족하느가'로" 처럼 문장 한가운데서 청크가 끊겼다.

그래서 이 버전은 먼저 텍스트를 "의미 단위"(제목 한 줄, 글머리 기호 한 항목,
빈 줄로 구분된 문단)로 나누고, 그 단위를 통째로만 청크에 채워 넣는다. 한 단위가
600자를 넘을 때만 그 단위 안에서 예외적으로 다시 쪼갠다 — 이때도 공백이 아니라
문장이 끝나는 지점을 우선한다.

## 왜 RecursiveCharacterTextSplitter는 fallback으로만 쓰는가
단순히 N자마다 자르면 문장이 중간에 끊겨 의미가 훼손된다. RecursiveCharacterTextSplitter는
문단(\n\n) → 줄바꿈(\n) → 문장 부호 → 글자 순으로 "더 큰 단위"부터 나눠보려고 시도한다.
의미 단위로 미리 나눠 놓았기 때문에, 이 fallback은 "단위 하나가 비정상적으로 긴 경우"에만
호출된다.
"""

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.pdf_extract import PageText

# 제목(상위 섹션) 후보로 볼 수 있는 줄의 패턴.
# "▶"는 실제 리포트(글로벌 ICT 월간동향리포트류)에서 대제목에 쓰는 기호라는 것을
# 실제 데이터로 확인하고 추가했다. 나머지(로마 숫자/번호/장절)는 다른 형식의 문서용 보수적 규칙.
# 숫자는 1~20으로 제한한다 — 제한 없이 허용하면 "607)CEN/CENELEC..." 같은 각주·참조
# 번호까지 제목으로 잘못 인식하는 것을 실제 문서에서 확인했다. 챕터/절 번호는
# 20을 넘는 경우가 드물어 이 범위로도 실질적인 손실은 거의 없다.
# 오탐이 나면 이전 섹션 이름이 계속 이어질 뿐이라 청크 텍스트 자체는 잃지 않는다.
_HEADING_RE = re.compile(
    r"^(?:▶|[Ⅰ-Ⅹ][.\)]|(?:[1-9]|1[0-9]|20)[.\)]|제?\s*[0-9]+\s*[장절]|[가-힣]\.)\s*\S"
)
_MAX_HEADING_LEN = 60

# 글머리 기호로 시작하는 줄 — 리포트에서 각 항목(•, ○, ➢)은 그 자체로 하나의 완결된
# 의미 단위다. 앞뒤에 빈 줄이 없어도 여기서 새 단위를 시작한다.
_BULLET_RE = re.compile(r"^[•○➢✓※▷◇\-]\s*\S")

# 단위 하나가 chunk_size를 넘길 때, 문장이 끝나는 지점을 우선해서 쪼갠다.
# 한국어 문장은 "~다./요./함./음." 뒤에 마침표가 오거나, 그냥 마침표/물음표/느낌표로 끝난다.
_SENTENCE_SEPARATORS = ["\n", "다. ", "요. ", "함. ", "음. ", ". ", "! ", "? ", " ", ""]


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
    if _HEADING_RE.match(stripped):
        return stripped
    return None


@dataclass
class _Unit:
    text: str
    is_heading: bool


def _segment_units(text: str) -> list[_Unit]:
    """페이지 텍스트를 제목/글머리 항목/문단 단위로 나눈다.

    같은 문단(또는 같은 글머리 항목) 안에서 줄바꿈된 부분은 공백으로 이어 붙인다 —
    PDF layout 추출은 원본의 시각적 줄바꿈을 그대로 살리기 때문에, 한 문장이 여러
    줄에 걸쳐 있는 경우가 흔하다. 이걸 그대로 두면 문단 하나가 여러 조각으로
    나뉘어 버린다.
    """
    units: list[_Unit] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            units.append(_Unit(text=" ".join(buffer), is_heading=False))
            buffer.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()  # 빈 줄 = 문단 구분
            continue

        heading = _detect_heading(line)
        if heading:
            flush()
            units.append(_Unit(text=heading, is_heading=True))
            continue

        if _BULLET_RE.match(line) and buffer:
            flush()  # 새 글머리 항목 = 이전 문단과 분리

        buffer.append(line)

    flush()
    return units


def _split_long_unit(text: str, chunk_size: int) -> list[str]:
    """단위 하나가 chunk_size를 넘기면 문장 경계 위주로 쪼갠다 (예외 상황용 fallback)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=0,
        separators=_SENTENCE_SEPARATORS,
    )
    return splitter.split_text(text)


def chunk_pages(
    pages: list[PageText],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """제목/문단 등 의미 단위를 기준으로 청킹한다.

    페이지 경계를 넘어 청크를 합치지 않는다 — 청크마다 정확한 page 메타데이터를
    붙여야 하기 때문이다 (CLAUDE.md: 메타데이터 누락 금지).
    """
    chunks: list[Chunk] = []
    current_section = ""  # 제목 미발견 상태 — 빈 문자열로 둔다 (화면에 "제목 없음" 노출 방지)

    for page in pages:
        units = _segment_units(page.text)

        buffer: list[str] = []
        buffer_len = 0

        def flush_chunk() -> None:
            nonlocal buffer, buffer_len
            if not buffer:
                return
            body = "\n".join(buffer)
            prefixed = f"[{current_section}] {body}" if current_section else body
            chunks.append(Chunk(page=page.page, section=current_section, text=prefixed))

            # overlap: 다음 청크 맨 앞에 이전 청크의 마지막 단위(들)를 다시 넣어
            # 문맥이 완전히 끊기지 않게 한다. 문자 수가 아니라 "단위" 단위로 넘겨준다 —
            # 그래야 문장 중간이 아니라 항상 문단/항목 경계에서 겹친다.
            carry: list[str] = []
            carry_len = 0
            for piece in reversed(buffer):
                if carry_len + len(piece) > chunk_overlap:
                    break
                carry.insert(0, piece)
                carry_len += len(piece)
            buffer = carry
            buffer_len = carry_len

        for unit in units:
            if unit.is_heading:
                # 새 섹션 제목을 만나면 이전 섹션 내용은 여기서 마무리한다.
                flush_chunk()
                current_section = unit.text
                pieces = [unit.text]
            elif len(unit.text) > chunk_size:
                pieces = _split_long_unit(unit.text, chunk_size)
            else:
                pieces = [unit.text]

            for piece in pieces:
                if buffer and buffer_len + len(piece) > chunk_size:
                    flush_chunk()
                    # flush 직후 되살아난 overlap carry조차 이 조각과 합치면 또
                    # chunk_size를 넘길 수 있다 (예: carry 90자 + 다음 조각 590자).
                    # 이 경우 carry를 포기한다 — 문맥 연결보다 크기 제한이 우선이다.
                    # (각 piece는 _split_long_unit()에서 이미 chunk_size 이하로
                    # 보장되므로, carry를 비우면 이 시점부터는 반드시 들어간다.)
                    if buffer and buffer_len + len(piece) > chunk_size:
                        buffer = []
                        buffer_len = 0
                buffer.append(piece)
                buffer_len += len(piece)

        flush_chunk()

    return chunks

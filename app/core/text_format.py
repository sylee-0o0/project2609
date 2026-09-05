"""검색 결과·문서 상세 화면에 보여줄 텍스트를 다듬는다.

여기서 하는 정리는 어디까지나 "화면에 보여줄 때"만 적용한다 — ChromaDB에 저장된
원문이나 임베딩 자체는 절대 건드리지 않는다. 그래야 나중에 "왜 이 청크가
검색됐는지"를 원본 그대로 추적할 수 있고, 재청킹 없이 표시 방식만 계속 개선할 수 있다.
"""

import re

# 청크 앞에 붙는 "[섹션명] " 형태의 prefix. 화면에는 section을 별도 필드로 이미
# 보여주고 있어서, 본문 안에 또 나오면 중복이라 제거한다.
_LEADING_BRACKET_PREFIX_RE = re.compile(r"^\[[^\]]*\]\s*")

# PDF layout 모드 추출 특성상 글자 사이에 불규칙하게 많은 공백이 들어간다
# (예: "글로벌      ICT"). 화면 표시용으로만 한 칸으로 줄인다. 　(전각 공백)도 포함.
_SPACE_RUN_RE = re.compile(r"[ \t　]{2,}")
_BLANK_LINES_RE = re.compile(r"\n{3,}")

_NO_TITLE_PLACEHOLDERS = {"(제목 없음)", ""}


def clean_section(section: str) -> str:
    """실제 제목을 못 찾은 경우("(제목 없음)" 등)는 화면에서 공란으로 보여준다."""
    return "" if section in _NO_TITLE_PLACEHOLDERS else section


def clean_text(text: str) -> str:
    """청크 앞 prefix 제거 + 과도한 공백/빈 줄 정리."""
    text = _LEADING_BRACKET_PREFIX_RE.sub("", text, count=1)
    text = _SPACE_RUN_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def merge_overlapping_texts(texts: list[str], max_overlap: int = 150, min_overlap: int = 15) -> str:
    """겹치는 청크(overlap)들을 이어붙이되, 겹치는 구간은 중복 출력하지 않는다.

    청킹 시 chunk_overlap(기본 100자)만큼 앞 청크의 꼬리가 다음 청크 앞부분에도
    다시 나온다 — 검색 품질에는 도움이 되지만, 문서를 통째로 이어 붙여 보여줄 때는
    같은 문장이 반복되어 읽기 불편하다. 그래서 "앞 청크의 끝부분과 다음 청크의
    시작부분이 겹치는 가장 긴 구간"을 찾아 그 부분만 제거하고 이어붙인다.

    완벽한 문장 단위 정렬은 아니지만(문자열 단순 비교), 화면 가독성 목적에는 충분하다.
    """
    if not texts:
        return ""

    merged = texts[0]
    for nxt in texts[1:]:
        overlap_len = 0
        limit = min(max_overlap, len(merged), len(nxt))
        for n in range(limit, min_overlap - 1, -1):
            if merged[-n:] == nxt[:n]:
                overlap_len = n
                break
        merged += "\n\n" + nxt[overlap_len:].lstrip()

    return merged

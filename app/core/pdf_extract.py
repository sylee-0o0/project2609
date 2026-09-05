"""PDF에서 텍스트를 추출한다.

## 한국어 처리 가장 큰 함정 (CLAUDE.md 참고)
PowerPoint로 만든 PDF를 pypdf 기본 모드로 추출하면 띄어쓰기가 사라지는 경우가 많다.
    예: "오픈뱅킹 데이터 이동성을 활용해" → "오픈뱅킹데이터이동성을활용해"

이는 PPT의 텍스트 상자가 글자 단위로 배치되어 PDF에 저장되기 때문에 생기는 문제로,
pypdf의 `extraction_mode="plain"`(기본값)은 글자를 읽는 순서를 좌표 기준으로 재조립하면서
공백 정보를 잃어버릴 수 있다. 반면 `extraction_mode="layout"`은 원본의 시각적 레이아웃을
최대한 유지하며 추출해서 이런 경우에 더 정확할 때가 많다.

하지만 layout 모드가 항상 더 나은 것은 아니다 (표가 많은 문서 등에서는 오히려 깨질 수 있음).
그래서 이 모듈은 **두 모드를 모두 시도**하고, 페이지별로 "한글 어절 수 / 한글 글자 수" 비율이
더 높은(=띄어쓰기가 잘 살아있는) 쪽을 채택한다.
"""

import re
from dataclasses import dataclass

from pypdf import PdfReader

# 한글 완성형 글자 범위 (가~힣)
_HANGUL_CHAR_RE = re.compile(r"[가-힣]")


@dataclass
class PageText:
    """한 페이지에서 추출된 텍스트와, 어떤 추출 모드를 채택했는지 기록."""

    page: int  # 1부터 시작하는 페이지 번호
    text: str
    extraction_mode: str  # "plain" 또는 "layout" — 디버깅/검증용


def _hangul_word_char_ratio(text: str) -> float:
    """한글 어절 수 / 한글 글자 수 비율을 계산한다.

    띄어쓰기가 사라진 텍스트는 긴 글자 덩어리가 하나의 "어절"로 뭉쳐지므로
    이 비율이 낮아진다. 반대로 띄어쓰기가 살아있으면 어절 수가 많아져 비율이 높아진다.
    한글이 아예 없는 페이지(표지, 빈 페이지 등)는 0.0을 반환해 비교에서 밀리게 한다.
    """
    hangul_chars = _HANGUL_CHAR_RE.findall(text)
    if not hangul_chars:
        return 0.0

    # "어절"은 공백으로 나눈 토큰 중 한글이 하나라도 포함된 것만 센다.
    hangul_words = [tok for tok in text.split() if _HANGUL_CHAR_RE.search(tok)]

    return len(hangul_words) / len(hangul_chars)


def extract_pdf_text(pdf_path: str) -> list[PageText]:
    """PDF 전체 페이지를 텍스트로 추출한다.

    페이지마다 plain 모드와 layout 모드를 모두 시도한 뒤,
    한글 어절/글자 비율이 더 높은 쪽을 채택한다.
    """
    reader = PdfReader(pdf_path)
    pages: list[PageText] = []

    for i, page in enumerate(reader.pages, start=1):
        plain_text = page.extract_text() or ""
        layout_text = page.extract_text(extraction_mode="layout") or ""

        plain_ratio = _hangul_word_char_ratio(plain_text)
        layout_ratio = _hangul_word_char_ratio(layout_text)

        if layout_ratio > plain_ratio:
            pages.append(PageText(page=i, text=layout_text, extraction_mode="layout"))
        else:
            pages.append(PageText(page=i, text=plain_text, extraction_mode="plain"))

    return pages


def preview_extraction(pages: list[PageText], chars_per_page: int = 200) -> str:
    """추출 결과를 사람이 눈으로 확인할 수 있는 문자열로 요약한다.

    CLAUDE.md: "추출 직후 텍스트를 눈으로 확인하는 단계를 넣는다.
    여기서 안 잡으면 원인을 못 찾는다." — 업로드 처리 중 이 함수의 결과를
    로그로 남기거나, 개발 중에는 scripts/preview_extract.py 같은 스크립트로
    직접 눈으로 확인한다.
    """
    lines = []
    for p in pages:
        snippet = p.text[:chars_per_page].replace("\n", " ")
        lines.append(f"[페이지 {p.page} / 모드: {p.extraction_mode}] {snippet}")
    return "\n".join(lines)

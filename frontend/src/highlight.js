// 검색 결과 스니펫에서 질문과 겹치는 단어를 표시하기 위한 유틸리티.
//
// 주의: bge-m3는 "의미"로 검색하는 dense 임베딩 모델이라, 질문과 문자 그대로
// 일치하지 않아도 관련 청크가 나올 수 있다. 그래서 이 하이라이트는 "왜 이 결과가
// 뽑혔는지"에 대한 완전한 설명이 아니라, 질문에 쓴 단어가 스니펫 어디에 그대로
// 나타나는지 보여주는 보조 표시일 뿐이다 (진짜 의미 기반 하이라이트를 하려면
// 1-C에서 다룰 키워드/토큰 단위 분석이 필요하다).

const STOPWORDS = new Set([
  '그리고', '그러나', '하지만', '그래서', '또는', '있다', '없다', '한다', '했다',
  '이다', '이란', '무엇', '어떤', '왜', '어떻게', '언제', '어디', '누가',
])

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * 질문 문자열에서 하이라이트에 쓸 토큰을 뽑는다.
 * 공백/문장부호로 나누고, 너무 짧거나(1글자) 불용어인 토큰은 뺀다.
 */
function extractTokens(query) {
  const raw = query.split(/[\s,.!?()'"'"“”‘’·:;]+/).filter(Boolean)
  const tokens = raw.filter((t) => t.length >= 2 && !STOPWORDS.has(t))
  // 긴 토큰을 먼저 매칭하도록 정렬 — 짧은 토큰이 긴 토큰의 일부만 하이라이트하는 것을 방지.
  return [...new Set(tokens)].sort((a, b) => b.length - a.length)
}

/**
 * text를 { text, highlight } 조각의 배열로 나눈다.
 * highlight: true인 조각을 <mark>로 감싸서 렌더링하면 된다.
 */
export function splitWithHighlights(text, query) {
  const tokens = extractTokens(query)
  if (tokens.length === 0) return [{ text, highlight: false }]

  const pattern = new RegExp(`(${tokens.map(escapeRegExp).join('|')})`, 'gi')
  const parts = text.split(pattern)

  // String.split(캡처 그룹 포함 정규식)은 매칭된 부분도 배열에 포함시켜 돌려주며,
  // 홀수 인덱스가 항상 매칭된 조각이다. 빈 문자열을 먼저 걸러내면 이 홀/짝
  // 대응이 깨지므로, highlight 여부를 먼저 붙이고 나서 빈 조각을 제거한다.
  return parts
    .map((part, i) => ({ text: part, highlight: i % 2 === 1 }))
    .filter((p) => p.text !== undefined && p.text !== '')
}

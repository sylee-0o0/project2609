import { useState } from 'react'

// 1-B: 질문을 입력하면 의미 기반으로 가장 유사한 청크 top_k개를 찾아 보여준다.
// 모든 결과에는 출처(파일명·페이지·섹션)를 반드시 표시한다 — 출처 없는 결과는 실패로 본다.
export default function SearchPanel() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [response, setResponse] = useState(null)

  async function handleSearch(event) {
    event.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return

    setLoading(true)
    setError(null)
    setResponse(null)

    try {
      const params = new URLSearchParams({ q: trimmed, top_k: '5' })
      const res = await fetch(`/api/search?${params}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `검색 실패 (HTTP ${res.status})`)
      }
      setResponse(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <form onSubmit={handleSearch} className="flex items-center gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="궁금한 내용을 질문처럼 입력하세요"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={!query.trim() || loading}
          className="shrink-0 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {loading ? '검색 중…' : '검색'}
        </button>
      </form>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {response?.message && <p className="mt-6 text-sm text-gray-500">{response.message}</p>}

      {response?.results?.length > 0 && (
        <ul className="mt-6 space-y-3">
          {response.results.map((r, i) => (
            <li key={r.chunk_id} className="rounded-md border border-gray-200 p-4 text-sm">
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>
                  #{i + 1} · 유사도 {(r.similarity * 100).toFixed(1)}%
                </span>
                {/* 출처: 파일명 · 페이지 (· 섹션, 있을 때만) — CLAUDE.md: 출처 없는 결과는 실패로 본다 */}
                <span>
                  {r.source} · {r.page}페이지
                  {r.section && ` · ${r.section}`}
                </span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-gray-800">{r.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

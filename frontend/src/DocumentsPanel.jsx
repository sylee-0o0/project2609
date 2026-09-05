import { useEffect, useState } from 'react'

// 현재 ChromaDB에 어떤 파일들이 저장되어 있는지 보여주고, 각 파일을 펼치면
// 본문을 한 문서처럼 이어서 읽을 수 있다 (임베딩 값은 아래에 따로 접어둔다).
// 삭제도 여기서 한다.
export default function DocumentsPanel() {
  const [documents, setDocuments] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [detailById, setDetailById] = useState({})
  const [detailError, setDetailError] = useState(null)
  const [showEmbeddings, setShowEmbeddings] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/documents')
      if (!res.ok) throw new Error(`목록을 불러오지 못했습니다 (HTTP ${res.status})`)
      const data = await res.json()
      setDocuments(data.documents)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function toggleExpand(documentId) {
    if (expandedId === documentId) {
      setExpandedId(null)
      return
    }
    setExpandedId(documentId)
    setShowEmbeddings(false)
    setDetailError(null)
    if (!detailById[documentId]) {
      try {
        const res = await fetch(`/api/documents/${documentId}/chunks`)
        if (!res.ok) throw new Error(`본문을 불러오지 못했습니다 (HTTP ${res.status})`)
        const data = await res.json()
        setDetailById((prev) => ({ ...prev, [documentId]: data }))
      } catch (err) {
        setDetailError(err.message)
      }
    }
  }

  async function handleDelete(documentId, source) {
    if (!window.confirm(`"${source}"을(를) 삭제할까요? 저장된 청크가 모두 지워집니다.`)) {
      return
    }
    setDeletingId(documentId)
    try {
      const res = await fetch(`/api/documents/${documentId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`삭제하지 못했습니다 (HTTP ${res.status})`)
      setDocuments((prev) => prev.filter((d) => d.document_id !== documentId))
      if (expandedId === documentId) setExpandedId(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) return <p className="text-sm text-gray-500">불러오는 중…</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">총 {documents.length}개 파일</p>
        <button type="button" onClick={load} className="text-sm text-indigo-600 hover:underline">
          새로고침
        </button>
      </div>

      {documents.length === 0 ? (
        <p className="mt-4 text-sm text-gray-500">아직 업로드된 파일이 없습니다.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {documents.map((d) => {
            const detail = detailById[d.document_id]
            const isExpanded = expandedId === d.document_id

            return (
              <li key={d.document_id} className="rounded-md border border-gray-200 text-sm">
                <div className="flex items-center justify-between p-3">
                  <button
                    type="button"
                    onClick={() => toggleExpand(d.document_id)}
                    className="flex-1 text-left font-medium text-gray-800 hover:text-indigo-600"
                  >
                    {isExpanded ? '▼' : '▶'} {d.source}
                  </button>
                  <span className="mx-3 text-gray-500">
                    {d.chunk_count}개 청크 · {new Date(d.uploaded_at).toLocaleString()}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDelete(d.document_id, d.source)}
                    disabled={deletingId === d.document_id}
                    className="shrink-0 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-40"
                  >
                    {deletingId === d.document_id ? '삭제 중…' : '삭제'}
                  </button>
                </div>

                {isExpanded && (
                  <div className="border-t border-gray-100 p-4">
                    {detailError && <p className="text-red-600">{detailError}</p>}
                    {!detailError && !detail && <p className="text-gray-500">불러오는 중…</p>}

                    {detail && (
                      <>
                        {/* 본문 전체를 청크 경계 없이 한 컨테이너 안에서 이어서 보여준다.
                            (겹치는 구간은 서버에서 이미 제거해서 붙여 보냄) */}
                        <div className="whitespace-pre-wrap rounded-md bg-gray-50 p-4 leading-relaxed text-gray-800">
                          {detail.merged_text}
                        </div>

                        <button
                          type="button"
                          onClick={() => setShowEmbeddings((v) => !v)}
                          className="mt-3 text-xs text-indigo-600 hover:underline"
                        >
                          {showEmbeddings ? '임베딩 값 숨기기' : '청크별 임베딩 값 보기'}
                        </button>

                        {showEmbeddings && (
                          <ul className="mt-2 space-y-1 font-mono text-xs text-gray-500">
                            {detail.chunks.map((c, i) => (
                              <li key={c.chunk_id}>
                                #{i + 1} ({c.page}페이지{c.section ? `, ${c.section}` : ''}) —{' '}
                                {c.embedding_dim}차원: [
                                {c.embedding_preview.map((v) => v.toFixed(4)).join(', ')}, …]
                              </li>
                            ))}
                          </ul>
                        )}
                      </>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

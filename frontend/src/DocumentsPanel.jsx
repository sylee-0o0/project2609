import { useEffect, useState } from 'react'

// 현재 ChromaDB에 어떤 파일들이 저장되어 있는지 보여주고, 각 파일을 펼치면
// 청크 원문과 임베딩 값을 확인할 수 있다. 삭제도 여기서 한다.
export default function DocumentsPanel() {
  const [documents, setDocuments] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [chunksById, setChunksById] = useState({})
  const [chunksError, setChunksError] = useState(null)
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
    setChunksError(null)
    if (!chunksById[documentId]) {
      try {
        const res = await fetch(`/api/documents/${documentId}/chunks`)
        if (!res.ok) throw new Error(`청크를 불러오지 못했습니다 (HTTP ${res.status})`)
        const data = await res.json()
        setChunksById((prev) => ({ ...prev, [documentId]: data.chunks }))
      } catch (err) {
        setChunksError(err.message)
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
          {documents.map((d) => (
            <li key={d.document_id} className="rounded-md border border-gray-200 text-sm">
              <div className="flex items-center justify-between p-3">
                <button
                  type="button"
                  onClick={() => toggleExpand(d.document_id)}
                  className="flex-1 text-left font-medium text-gray-800 hover:text-indigo-600"
                >
                  {expandedId === d.document_id ? '▼' : '▶'} {d.source}
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

              {expandedId === d.document_id && (
                <div className="border-t border-gray-100 p-3">
                  {chunksError && <p className="text-red-600">{chunksError}</p>}
                  {!chunksError && !chunksById[d.document_id] && (
                    <p className="text-gray-500">청크를 불러오는 중…</p>
                  )}
                  {chunksById[d.document_id]?.map((c, i) => (
                    <div
                      key={c.chunk_id}
                      className="mb-3 rounded border border-gray-100 bg-gray-50 p-3 last:mb-0"
                    >
                      <p className="text-xs text-gray-500">
                        #{i + 1} · {c.page}페이지 · {c.section}
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-gray-800">{c.text}</p>
                      <p className="mt-2 break-all font-mono text-xs text-gray-400">
                        임베딩({c.embedding_dim}차원): [
                        {c.embedding_preview.map((v) => v.toFixed(4)).join(', ')}, …]
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

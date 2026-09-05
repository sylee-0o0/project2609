import { useEffect, useState } from 'react'

// 현재 ChromaDB에 어떤 파일들이 저장되어 있는지 보여준다.
export default function DocumentsPanel() {
  const [documents, setDocuments] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

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

  if (loading) return <p className="text-sm text-gray-500">불러오는 중…</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">총 {documents.length}개 파일</p>
        <button
          type="button"
          onClick={load}
          className="text-sm text-indigo-600 hover:underline"
        >
          새로고침
        </button>
      </div>

      {documents.length === 0 ? (
        <p className="mt-4 text-sm text-gray-500">아직 업로드된 파일이 없습니다.</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {documents.map((d) => (
            <li
              key={d.document_id}
              className="flex items-center justify-between rounded-md border border-gray-200 p-3 text-sm"
            >
              <span className="font-medium text-gray-800">{d.source}</span>
              <span className="text-gray-500">
                {d.chunk_count}개 청크 · {new Date(d.uploaded_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

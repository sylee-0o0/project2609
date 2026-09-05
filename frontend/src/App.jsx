import { useEffect, useState } from 'react'

// 1-A 단계 스켈레톤: PDF 업로드 → 처리 진행 상태 확인.
// 검색 UI(1-B)는 아직 만들지 않는다 — CLAUDE.md: "지시받지 않은 단계를 미리 만들지 않는다".
export default function App() {
  const [file, setFile] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [uploadError, setUploadError] = useState(null)

  // job_id가 생기면 SSE(EventSource)로 진행 상태를 구독한다.
  // EventSource는 반드시 useEffect의 cleanup에서 close()해야 한다 — 안 하면
  // React StrictMode의 개발 모드 이중 렌더링 시 연결이 두 배로 쌓인다.
  // (CLAUDE.md: StrictMode를 꺼서 이 문제를 "해결"하지 않는다 — cleanup을 제대로 한다.)
  useEffect(() => {
    if (!jobId) return

    const source = new EventSource(`/api/jobs/${jobId}/events`)

    source.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setJob(data)
      if (data.status === 'done' || data.status === 'failed') {
        source.close()
      }
    }

    source.onerror = () => {
      // 서버가 스트림을 정상 종료해도 브라우저가 onerror를 한 번 더 쏠 수 있으므로
      // 여기서는 연결만 정리하고 별도 에러 메시지는 띄우지 않는다.
      source.close()
    }

    return () => source.close()
  }, [jobId])

  async function handleUpload(event) {
    event.preventDefault()
    if (!file) return

    setUploadError(null)
    setJob(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/upload', { method: 'POST', body: formData })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `업로드 실패 (HTTP ${res.status})`)
      }
      const data = await res.json()
      setJobId(data.job_id)
    } catch (err) {
      setUploadError(err.message)
    }
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-12">
      <h1 className="text-2xl font-semibold text-gray-900">글로벌 ICT 동향 리포트 조회</h1>
      <p className="mt-1 text-sm text-gray-500">
        1-A: PDF 업로드 → 텍스트 추출 → 청킹 → 임베딩 → ChromaDB 저장
      </p>

      <form onSubmit={handleUpload} className="mt-8 flex items-center gap-3">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-gray-700 file:mr-3 file:rounded-md file:border-0 file:bg-gray-900 file:px-3 file:py-2 file:text-sm file:text-white"
        />
        <button
          type="submit"
          disabled={!file}
          className="shrink-0 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          업로드
        </button>
      </form>

      {uploadError && <p className="mt-4 text-sm text-red-600">{uploadError}</p>}

      {job && (
        <div className="mt-6 rounded-md border border-gray-200 p-4 text-sm">
          <p>
            <span className="font-medium">{job.filename}</span> — 상태:{' '}
            <span className="font-mono">{job.status}</span>
          </p>
          <p className="mt-1 text-gray-600">{job.message}</p>
          {job.chunk_count != null && (
            <p className="mt-1 text-gray-600">저장된 청크 수: {job.chunk_count}</p>
          )}
          {job.error && <p className="mt-1 text-red-600">{job.error}</p>}
        </div>
      )}
    </div>
  )
}

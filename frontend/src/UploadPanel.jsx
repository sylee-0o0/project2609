import { useEffect, useState } from 'react'

// 1-A: PDF 업로드 → 처리 진행 상태 확인.
export default function UploadPanel() {
  const [file, setFile] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [connectionLost, setConnectionLost] = useState(false)

  const TERMINAL_STATUSES = ['done', 'failed', 'duplicate']

  // job_id가 생기면 SSE(EventSource)로 진행 상태를 구독한다.
  // EventSource는 반드시 useEffect의 cleanup에서 close()해야 한다 — 안 하면
  // React StrictMode의 개발 모드 이중 렌더링 시 연결이 두 배로 쌓인다.
  // (CLAUDE.md: StrictMode를 꺼서 이 문제를 "해결"하지 않는다 — cleanup을 제대로 한다.)
  useEffect(() => {
    if (!jobId) return

    setConnectionLost(false)
    const source = new EventSource(`/api/jobs/${jobId}/events`)

    source.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setJob(data)
      if (TERMINAL_STATUSES.includes(data.status)) {
        source.close()
      }
    }

    // 개발 서버 재시작, 네트워크 끊김 등으로 스트림이 죽으면 onerror가 온다.
    // 그냥 닫기만 하면 화면이 마지막으로 받은 상태(예: "storing")에서 그대로
    // 멈춘 것처럼 보인다 — 실제로는 서버가 이미 끝냈는데 알림만 못 받은 것일 수도
    // 있으므로, REST로 한 번 더 진짜 상태를 확인해서 화면을 맞춰준다.
    source.onerror = async () => {
      source.close()
      try {
        const res = await fetch(`/api/jobs/${jobId}`)
        if (res.ok) {
          setJob(await res.json())
        } else {
          // 404 등 — 서버가 재시작되어 작업 기록이 사라진 경우 (메모리 저장소라
          // 프로세스 재시작 시 사라진다).
          setConnectionLost(true)
        }
      } catch {
        setConnectionLost(true)
      }
    }

    return () => source.close()
  }, [jobId])

  async function handleUpload(event) {
    event.preventDefault()
    if (!file) return

    setUploadError(null)
    setJob(null)
    setConnectionLost(false)

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
    <div>
      <form onSubmit={handleUpload} className="flex items-center gap-3">
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

      {connectionLost && (
        <p className="mt-6 text-sm text-amber-600">
          서버와의 연결이 끊어져 진행 상태를 더 이상 확인할 수 없습니다. (개발 서버가
          재시작되었을 수 있습니다.) 목록에서 저장 여부를 확인하거나 다시 업로드해 주세요.
        </p>
      )}

      {job && (
        <div
          className={
            'mt-6 rounded-md border p-4 text-sm ' +
            (job.status === 'duplicate'
              ? 'border-amber-200 bg-amber-50'
              : 'border-gray-200')
          }
        >
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

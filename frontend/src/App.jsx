import { useState } from 'react'
import SearchPanel from './SearchPanel'
import UploadPanel from './UploadPanel'

const TABS = [
  { key: 'search', label: '검색' },
  { key: 'upload', label: '업로드' },
]

export default function App() {
  const [tab, setTab] = useState('search')

  return (
    <div className="mx-auto max-w-xl px-6 py-12">
      <h1 className="text-2xl font-semibold text-gray-900">글로벌 ICT 동향 리포트 조회</h1>
      <p className="mt-1 text-sm text-gray-500">
        PDF를 업로드하고, 의미가 비슷한 내용을 질문으로 검색해 보세요.
      </p>

      <div className="mt-8 flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={
              'px-4 py-2 text-sm font-medium ' +
              (tab === t.key
                ? 'border-b-2 border-indigo-600 text-indigo-600'
                : 'text-gray-500 hover:text-gray-700')
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === 'search' ? <SearchPanel /> : <UploadPanel />}
      </div>
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import {
  addTasks,
  clearFinished,
  clearHistory,
  getConfig,
  getHistory,
  getTasks,
  pauseTask,
  retryFailed,
  resumeTask,
  setConcurrency,
  type Task,
} from './api'
import './App.css'

function App() {
  const [links, setLinks] = useState('')
  const [presets, setPresets] = useState<string[]>([])
  const [preset, setPreset] = useState('')
  const [outDir, setOutDir] = useState('')
  const [tasks, setTasks] = useState<Task[]>([])
  const [history, setHistory] = useState<Record<string, unknown>[]>([])
  const [concurrency, setLocalConcurrency] = useState(2)
  const [message, setMessage] = useState('正在连接本地后端...')

  const runningCount = tasks.filter((task) => task.status === '下载中').length
  const pendingCount = tasks.filter((task) => task.status === '等待中').length
  const selectedTask = tasks[0]

  const urls = useMemo(
    () => links.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
    [links],
  )

  async function refresh() {
    const [taskList, historyList] = await Promise.all([getTasks(), getHistory()])
    setTasks(taskList)
    setHistory(historyList)
  }

  useEffect(() => {
    getConfig()
      .then((config) => {
        setPresets(config.presets)
        setPreset(config.presets[0] ?? '')
        setOutDir(config.defaultOutDir)
        setMessage('后端已连接,可以开始下载。')
      })
      .then(refresh)
      .catch(() => setMessage('未连接后端: 请先启动 Python API 服务。'))
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])

  async function handleAdd() {
    if (!urls.length) {
      setMessage('请先粘贴至少一个链接。')
      return
    }
    await addTasks(urls.slice(0, 30), preset, outDir)
    setLinks('')
    setMessage(`已加入 ${Math.min(urls.length, 30)} 个任务。`)
    await refresh()
  }

  async function handleConcurrency(value: number) {
    setLocalConcurrency(value)
    await setConcurrency(value)
  }

  async function handlePauseResume() {
    if (!selectedTask) {
      setMessage('当前没有可操作任务。')
      return
    }
    if (selectedTask.status === '已暂停') {
      await resumeTask(selectedTask.id)
    } else {
      await pauseTask(selectedTask.id)
    }
    await refresh()
  }

  return (
    <main className="app-shell">
      <section className="hero-panel" aria-labelledby="page-title">
        <div className="hero-copy">
          <span className="eyebrow">Personal media downloader</span>
          <h1 id="page-title">把链接丢进来,剩下交给队列。</h1>
          <p>
            面向日常使用的多平台下载器。批量粘贴、自动识别、清晰度选择、下载进度和历史记录集中在一个界面里。
          </p>
        </div>
        <div className="status-card" aria-label="当前下载状态">
          <div>
            <span className="metric">{runningCount}</span>
            <span className="label">运行中</span>
          </div>
          <div>
            <span className="metric">{pendingCount}</span>
            <span className="label">等待中</span>
          </div>
          <div>
            <span className="metric">{concurrency}</span>
            <span className="label">并发数</span>
          </div>
        </div>
      </section>

      <section className="workspace-grid">
        <form className="input-card" aria-label="添加下载任务">
          <div className="section-head">
            <div>
              <h2>链接下载</h2>
              <p>每行一个链接,最多一次加入30条。</p>
            </div>
            <button className="ghost-button" type="button">
              粘贴
            </button>
          </div>

          <label className="field-label" htmlFor="links">
            分享链接
          </label>
          <textarea
            id="links"
            placeholder="https://www.youtube.com/watch?v=..."
            rows={6}
            value={links}
            onChange={(event) => setLinks(event.currentTarget.value)}
          />

          <div className="control-row">
            <label>
              下载格式
              <select value={preset} onChange={(event) => setPreset(event.target.value)}>
                {presets.map((preset) => (
                  <option key={preset}>{preset}</option>
                ))}
              </select>
            </label>
            <label>
              保存路径
              <input value={outDir} onChange={(event) => setOutDir(event.target.value)} />
            </label>
          </div>

          <div className="actions">
            <button className="primary-button" type="button" onClick={handleAdd}>
              加入队列
            </button>
            <label className="concurrency-control">
              并发数
              <input
                min={1}
                max={8}
                type="number"
                value={concurrency}
                onChange={(event) => handleConcurrency(Number(event.target.value))}
              />
            </label>
          </div>
          <p className="inline-message">{message}</p>
        </form>

        <aside className="tips-card">
          <h2>当前支持</h2>
          <div className="platform-list">
            {['YouTube', 'Bilibili', 'Twitter', 'TikTok', 'Instagram', 'Vimeo'].map(
              (name) => (
                <span key={name}>{name}</span>
              ),
            )}
          </div>
          <p>
            高清视频优先使用 MKV 保留音画质量;需要通用播放器兼容时选择 MP4 档。
          </p>
        </aside>
      </section>

      <section className="content-grid">
        <div className="panel queue-panel">
          <div className="section-head">
            <div>
              <h2>下载队列</h2>
              <p>实时进度、规格、速度和任务状态。</p>
            </div>
            <div className="button-group">
              <button type="button" onClick={handlePauseResume}>暂停/继续首个任务</button>
              <button type="button" onClick={() => retryFailed().then(refresh)}>重试失败</button>
              <button type="button" onClick={() => clearFinished().then(refresh)}>清除完成</button>
            </div>
          </div>

          <div className="task-list" aria-label="下载任务列表">
            {tasks.length === 0 && <p className="empty-text">暂无任务。粘贴链接后加入队列。</p>}
            {tasks.map((task) => (
              <article className="task-item" key={task.id}>
                <div>
                  <h3>{task.display_title}</h3>
                  <p>{task.url}</p>
                </div>
                <span className="spec-pill">{task.spec_text || '识别中'}</span>
                <span className="status-pill">{task.status}</span>
                <div className="progress-track" aria-label={`进度 ${task.progress}%`}>
                  <span style={{ width: `${task.progress}%` }} />
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="panel history-panel">
          <div className="section-head">
            <div>
              <h2>历史记录</h2>
              <p>完成或失败后自动保存在本机。</p>
            </div>
            <button type="button" onClick={() => clearHistory().then(refresh)}>清空历史</button>
          </div>

          <div className="history-list" aria-label="历史记录列表">
            {history.length === 0 && <p className="empty-text">暂无历史记录。</p>}
            {history.map((item, index) => (
              <article className="history-item" key={`${item.title}-${index}`}>
                <div>
                  <h3>{String(item.title || item.url || '未知任务')}</h3>
                  <p>{String(item.spec_text || item.filepath || '已保存')}</p>
                </div>
                <span>{String(item.status || '')}</span>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}

export default App

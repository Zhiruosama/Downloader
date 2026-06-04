import { useEffect, useMemo, useState } from 'react'
import {
  addTasks,
  clearFinished,
  clearHistory,
  getConfig,
  getHistory,
  getTasks,
  pauseTask,
  probeUrl,
  retryFailed,
  resumeTask,
  saveConfig,
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
  const [filenameTemplate, setFilenameTemplate] = useState('%(title)s.%(ext)s')
  const [cookieFile, setCookieFile] = useState('')
  const [probeLink, setProbeLink] = useState('')
  const [probeResult, setProbeResult] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [settingsClosing, setSettingsClosing] = useState(false)
  const [presetOpen, setPresetOpen] = useState(false)
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
        setPreset(config.defaultPreset || config.presets[0] || '')
        setOutDir(config.defaultOutDir)
        setLocalConcurrency(config.concurrency)
        setFilenameTemplate(config.filenameTemplate)
        setCookieFile(config.cookies.cookieFile)
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

  async function handleSaveSettings() {
    const config = await saveConfig({
      presets,
      defaultOutDir: outDir,
      defaultPreset: preset,
      filenameTemplate,
      concurrency,
      cookies: {
        mode: cookieFile ? 'file' : 'off',
        browser: 'edge',
        cookieFile,
      },
    })
    setPreset(config.defaultPreset)
    setOutDir(config.defaultOutDir)
    setLocalConcurrency(config.concurrency)
    setFilenameTemplate(config.filenameTemplate)
    setCookieFile(config.cookies.cookieFile)
    setMessage('设置已保存,后续任务会使用新配置。')
    closeSettings()
  }

  function openSettings() {
    setSettingsClosing(false)
    setShowSettings(true)
  }

  function closeSettings() {
    setSettingsClosing(true)
    window.setTimeout(() => {
      setShowSettings(false)
      setSettingsClosing(false)
    }, 180)
  }

  async function handleProbe() {
    if (!probeLink.trim()) {
      setProbeResult('请输入一个用于测试的链接。')
      return
    }
    setProbeResult('正在测试 cookies...')
    try {
      const result = await probeUrl(probeLink.trim())
      setProbeResult(
        `解析成功: ${result.title} · 最高可用 ${result.maxHeight || '未知'}p`,
      )
    } catch (error) {
      setProbeResult(`解析失败: ${String(error)}`)
    }
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
      <section className="topbar" aria-labelledby="page-title">
        <div className="topbar-spacer" aria-hidden="true" />
        <h1 className="brand-logo" id="page-title">Downloader</h1>
        <div className="topbar-status" aria-label="当前下载状态">
          <span><strong>{runningCount}</strong> 运行中</span>
          <span><strong>{pendingCount}</strong> 等待中</span>
          <span><strong>{concurrency}</strong> 并发</span>
          <button type="button" onClick={showSettings ? closeSettings : openSettings}>
            {showSettings ? '收起设置' : '设置'}
          </button>
        </div>
      </section>

      <section className="download-card">
        <form className="input-card" aria-label="添加下载任务">
          <div className="section-head">
            <div>
              <h2>粘贴链接（视频/图片/音频/直播）</h2>
              <p>每行一个链接,最多一次加入30条。公开内容直接下载,登录内容可在设置里启用 cookies。</p>
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

          <div className="download-options-row">
            <label>
              下载格式
              <div className="custom-select">
                <button
                  aria-expanded={presetOpen}
                  className="custom-select-trigger"
                  type="button"
                  onClick={() => setPresetOpen((value) => !value)}
                >
                  <span>{preset || '请选择格式'}</span>
                  <i aria-hidden="true" />
                </button>
                {presetOpen && (
                  <div className="custom-select-menu" role="listbox">
                    {presets.map((item) => (
                      <button
                        className={item === preset ? 'custom-option active' : 'custom-option'}
                        key={item}
                        role="option"
                        type="button"
                        aria-selected={item === preset}
                        onClick={() => {
                          setPreset(item)
                          setPresetOpen(false)
                        }}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </label>
            <label>
              保存路径
              <input value={outDir} onChange={(event) => setOutDir(event.target.value)} />
            </label>
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
            <button className="primary-button add-button" type="button" onClick={handleAdd}>
              加入队列
            </button>
          </div>
          <p className="inline-message">{message}</p>
          <div className="platform-strip">
            {['YouTube', 'Bilibili', 'Twitter', 'TikTok', 'Instagram', 'Vimeo', 'Reddit', 'Twitch'].map(
              (name) => (
                <span key={name}>{name}</span>
              ),
            )}
            <small>以及 yt-dlp 支持的更多平台</small>
          </div>
        </form>
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
              <p>完成后自动保存。</p>
            </div>
            <button className="clear-history-button" type="button" onClick={() => clearHistory().then(refresh)}>
              清空历史
            </button>
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
      {showSettings && (
        <div
          className={settingsClosing ? 'settings-overlay closing' : 'settings-overlay'}
          role="presentation"
          onClick={closeSettings}
        >
          <aside
            aria-label="下载设置"
            aria-modal="true"
            className={settingsClosing ? 'settings-drawer closing' : 'settings-drawer'}
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="drawer-head">
              <div>
                <h2>下载设置</h2>
                <p>默认值、命名模板和 cookies 登录方式。</p>
              </div>
              <button type="button" onClick={closeSettings}>关闭</button>
            </div>

            <div className="drawer-body">
              <div className="settings-grid">
                <label>
                  默认画质
                  <select value={preset} onChange={(event) => setPreset(event.target.value)}>
                    {presets.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  命名模板
                  <input
                    value={filenameTemplate}
                    onChange={(event) => setFilenameTemplate(event.target.value)}
                    placeholder="%(title)s.%(ext)s"
                  />
                </label>
                <label className="wide-field">
                  cookies.txt 路径(高级备用)
                  <input
                    value={cookieFile}
                    onChange={(event) => setCookieFile(event.target.value)}
                    placeholder="C:\\path\\to\\cookies.txt"
                  />
                </label>
              </div>
              <div className="cookie-help-card">
                <strong>Cookies 备用方案</strong>
                <ol>
                  <li>在浏览器登录目标网站。</li>
                  <li>导出 Netscape 格式 cookies.txt。</li>
                  <li>填写 cookies.txt 路径并保存。</li>
                </ol>
                <p>默认不使用登录态。cookies.txt 只作为高级备用方案。</p>
                <div className="probe-row">
                  <input
                    value={probeLink}
                    onChange={(event) => setProbeLink(event.target.value)}
                    placeholder="粘贴一个链接测试 cookies 是否有效"
                  />
                  <button type="button" onClick={handleProbe}>测试 cookies</button>
                </div>
                {probeResult && <p className="probe-result">{probeResult}</p>}
              </div>
            </div>
            <div className="drawer-actions">
              <button className="secondary-button" type="button" onClick={closeSettings}>
                取消
              </button>
              <button className="primary-button" type="button" onClick={handleSaveSettings}>
                保存设置
              </button>
            </div>
          </aside>
        </div>
      )}
    </main>
  )
}

export default App

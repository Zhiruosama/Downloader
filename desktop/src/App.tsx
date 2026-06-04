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
  type Config,
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
  const [cookieMode, setCookieMode] = useState<Config['cookies']['mode']>('off')
  const [cookieBrowser, setCookieBrowser] = useState<Config['cookies']['browser']>('chrome')
  const [cookieFile, setCookieFile] = useState('')
  const [probeLink, setProbeLink] = useState('')
  const [probeResult, setProbeResult] = useState('')
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
        setCookieMode(config.cookies.mode)
        setCookieBrowser(config.cookies.browser)
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
        mode: cookieMode,
        browser: cookieBrowser,
        cookieFile,
      },
    })
    setPreset(config.defaultPreset)
    setOutDir(config.defaultOutDir)
    setLocalConcurrency(config.concurrency)
    setFilenameTemplate(config.filenameTemplate)
    setCookieMode(config.cookies.mode)
    setCookieBrowser(config.cookies.browser)
    setCookieFile(config.cookies.cookieFile)
    setMessage('设置已保存,后续任务会使用新配置。')
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

  const cookieHelp =
    cookieMode === 'browser'
      ? `将读取 ${cookieBrowser} 的登录态。使用前请先在该浏览器登录目标网站,并关闭正在播放/下载占用的页面。`
      : cookieMode === 'file'
        ? '适合高级用户: 从浏览器导出 Netscape cookies.txt 后,把文件路径填到下方。'
        : '默认不使用登录态。公开内容可直接下载,会员/私密/年龄限制内容可能失败或没有高清。'

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
          <h2>登录与高清资源</h2>
          <div className="platform-list">
            {['YouTube', 'Bilibili', 'Twitter', 'TikTok', 'Instagram', 'Vimeo'].map(
              (name) => (
                <span key={name}>{name}</span>
              ),
            )}
          </div>
          <p>
            部分高清、会员或私密内容需要 cookies。请确保你已在对应浏览器登录,然后在下方设置中启用浏览器 cookies。
          </p>
        </aside>
      </section>

      <section className="panel settings-panel" aria-label="下载设置">
        <div className="section-head">
          <div>
            <h2>下载设置</h2>
            <p>保存默认路径、画质、命名模板和 cookies 登录方式。</p>
          </div>
          <button type="button" onClick={handleSaveSettings}>保存设置</button>
        </div>

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
          <div className="wide-field">
            <span className="field-title">Cookies 登录方式</span>
            <div className="cookie-mode-grid" role="group" aria-label="Cookies 登录方式">
              <button
                className={cookieMode === 'off' ? 'choice-card active' : 'choice-card'}
                type="button"
                onClick={() => setCookieMode('off')}
              >
                <strong>不使用</strong>
                <span>公开内容直接下载</span>
              </button>
              <button
                className={cookieMode === 'browser' ? 'choice-card active' : 'choice-card'}
                type="button"
                onClick={() => setCookieMode('browser')}
              >
                <strong>读取浏览器</strong>
                <span>推荐,不保存账号密码</span>
              </button>
              <button
                className={cookieMode === 'file' ? 'choice-card active' : 'choice-card'}
                type="button"
                onClick={() => setCookieMode('file')}
              >
                <strong>cookies.txt</strong>
                <span>手动导入文件</span>
              </button>
            </div>
          </div>
          <div className={cookieMode === 'browser' ? '' : 'is-muted'}>
            <span className="field-title">浏览器</span>
            <div className="browser-choice-grid" role="group" aria-label="浏览器选择">
              {(['chrome', 'edge', 'firefox'] as const).map((browser) => (
                <button
                  className={cookieBrowser === browser ? 'browser-pill active' : 'browser-pill'}
                  disabled={cookieMode !== 'browser'}
                  key={browser}
                  type="button"
                  onClick={() => setCookieBrowser(browser)}
                >
                  {browser === 'chrome' ? 'Chrome' : browser === 'edge' ? 'Edge' : 'Firefox'}
                </button>
              ))}
            </div>
          </div>
          <label className="wide-field">
            cookies.txt 路径
            <input
              value={cookieFile}
              disabled={cookieMode !== 'file'}
              onChange={(event) => setCookieFile(event.target.value)}
              placeholder="C:\\path\\to\\cookies.txt"
            />
          </label>
        </div>
        <div className="cookie-help-card">
          <strong>如何使用 Cookies 下载高清/私密内容</strong>
          <ol>
            <li>先在 Chrome / Edge / Firefox 登录目标网站。</li>
            <li>选择“读取浏览器”,并选中对应浏览器。</li>
            <li>保存设置后再加入下载任务。</li>
          </ol>
          <p>{cookieHelp}</p>
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

export const API_BASE = 'http://127.0.0.1:8765'

export type Task = {
  id: number
  url: string
  preset: string
  out_dir: string
  display_title: string
  status: string
  progress: number
  speed: number
  eta: number
  error: string
  spec_text: string
  filepath: string
}

export type Config = {
  presets: string[]
  defaultOutDir: string
  defaultPreset: string
  filenameTemplate: string
  concurrency: number
  cookies: {
    mode: 'off' | 'browser' | 'file'
    browser: 'chrome' | 'edge' | 'firefox'
    cookieFile: string
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json() as Promise<T>
}

export function getConfig() {
  return request<Config>('/api/config')
}

export function saveConfig(config: Config) {
  return request<Config>('/api/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })
}

export function probeUrl(url: string) {
  return request<{
    title: string
    uploader: string
    duration: number
    maxHeight: number
    url: string
  }>('/api/probe', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

export function getTasks() {
  return request<Task[]>('/api/tasks')
}

export function addTasks(urls: string[], preset: string, outDir: string) {
  return request<Task[]>('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({ urls, preset, out_dir: outDir }),
  })
}

export function pauseTask(taskId: number) {
  return request<{ ok: boolean }>(`/api/tasks/${taskId}/pause`, { method: 'POST' })
}

export function resumeTask(taskId: number) {
  return request<{ ok: boolean }>(`/api/tasks/${taskId}/resume`, { method: 'POST' })
}

export function retryFailed() {
  return request<{ ok: boolean }>('/api/tasks/retry-failed', { method: 'POST' })
}

export function clearFinished() {
  return request<{ ok: boolean }>('/api/tasks/clear-finished', { method: 'POST' })
}

export function setConcurrency(value: number) {
  return request<{ ok: boolean }>('/api/concurrency', {
    method: 'POST',
    body: JSON.stringify({ value }),
  })
}

export function getHistory() {
  return request<Record<string, unknown>[]>('/api/history')
}

export function clearHistory() {
  return request<{ ok: boolean }>('/api/history/clear', { method: 'POST' })
}

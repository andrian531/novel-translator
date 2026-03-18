const KEY = 'reader_progress'

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') } catch { return {} }
}

export function saveProgress(novelId, filename) {
  const p = load()
  p[novelId] = filename
  localStorage.setItem(KEY, JSON.stringify(p))
}

export function getProgress(novelId) {
  return load()[novelId] || null
}

export function getAllProgress() {
  return load()
}

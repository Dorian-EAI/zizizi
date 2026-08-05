const { createDesignPage } = require('./design-page-runtime')
const { formatTime, timeAgo } = require('./format')

function createRuntimePage(meta, extension) {
  const base = createDesignPage(meta)
  const extra = extension || {}
  return Object.assign({}, base, extra, {
    data: Object.assign({}, base.data, extra.data || {})
  })
}

function listFrom(value) {
  if (Array.isArray(value)) return value
  if (!value || typeof value !== 'object') return []
  for (const key of ['list', 'items', 'records', 'data']) {
    if (Array.isArray(value[key])) return value[key]
  }
  return []
}

function messageOf(error, fallback) {
  return String(error && (error.message || error.errMsg) || fallback || '加载失败')
}

function displayTime(value, full) {
  if (!value) return ''
  return full ? formatTime(value, 'YYYY-MM-DD HH:mm') : timeAgo(value)
}

function stars(value) {
  const rating = Math.max(0, Math.min(5, Math.round(Number(value) || 0)))
  return '★'.repeat(rating) + '☆'.repeat(5 - rating)
}

function initial(value, fallback) {
  const text = String(value || '').trim()
  return text ? text.slice(0, 1) : (fallback || '家')
}

module.exports = {
  createRuntimePage,
  displayTime,
  initial,
  listFrom,
  messageOf,
  stars
}

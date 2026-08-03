// utils/format.js — 格式化工具

// 时间格式化
function formatTime(date, fmt) {
  if (!date) date = new Date()
  if (typeof date === 'number' || typeof date === 'string') date = new Date(date)
  const o = {
    'M+': date.getMonth() + 1,
    'D+': date.getDate(),
    'H+': date.getHours(),
    'm+': date.getMinutes(),
    's+': date.getSeconds()
  }
  if (/(Y+)/.test(fmt)) {
    fmt = fmt.replace(RegExp.$1, (date.getFullYear() + '').substr(4 - RegExp.$1.length))
  }
  for (const k in o) {
    if (new RegExp('(' + k + ')').test(fmt)) {
      fmt = fmt.replace(RegExp.$1, RegExp.$1.length === 1 ? o[k] : ('00' + o[k]).substr(('' + o[k]).length))
    }
  }
  return fmt
}

// 相对时间
function timeAgo(timestamp) {
  const now = Date.now()
  const diff = now - new Date(timestamp).getTime()
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (diff < minute) return '刚刚'
  if (diff < hour) return Math.floor(diff / minute) + '分钟前'
  if (diff < day) return Math.floor(diff / hour) + '小时前'
  if (diff < 7 * day) return Math.floor(diff / day) + '天前'
  return formatTime(timestamp, 'MM-DD HH:mm')
}

// 价格格式化（分 -> 元）
function formatPrice(fen) {
  if (typeof fen !== 'number') fen = Number(fen) || 0
  return (fen / 100).toFixed(2)
}

// 金额展示（元，带千分位）
function formatMoney(yuan) {
  if (typeof yuan !== 'number') yuan = Number(yuan) || 0
  return yuan.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 距离格式化
function formatDistance(km) {
  if (km < 1) return Math.round(km * 1000) + 'm'
  return km.toFixed(1) + 'km'
}

// 手机号脱敏
function maskPhone(phone) {
  if (!phone || phone.length !== 11) return phone || ''
  return phone.substr(0, 3) + '****' + phone.substr(7)
}

// 问候语
function greeting() {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好'
  if (h < 9) return '早上好'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

module.exports = {
  formatTime,
  timeAgo,
  formatPrice,
  formatMoney,
  formatDistance,
  maskPhone,
  greeting
}

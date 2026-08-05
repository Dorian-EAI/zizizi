function finiteNumber(value, fallback) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : (fallback === undefined ? 0 : fallback)
}

function money(value) {
  return finiteNumber(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

function dateTime(value) {
  if (!value) return '时间待确认'
  const normalized = typeof value === 'string' && value.indexOf('T') < 0
    ? value.replace(' ', 'T') + 'Z'
    : value
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = number => String(number).padStart(2, '0')
  return [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate())].join('-') +
    ' ' + [pad(date.getHours()), pad(date.getMinutes())].join(':')
}

const TYPE_PRESENTATION = {
  income: { label: '服务收入', icon: '收', sign: '+', tone: 'success' },
  recharge: { label: '微信充值', icon: '充', sign: '+', tone: 'success' },
  refund: { label: '退款到账', icon: '退', sign: '+', tone: 'success' },
  expense: { label: '订单支付', icon: '支', sign: '-', tone: 'danger' },
  withdraw: { label: '提现申请', icon: '提', sign: '-', tone: 'danger' }
}

const STATUS_PRESENTATION = {
  success: { label: '成功', tone: 'success' },
  paid: { label: '已支付', tone: 'success' },
  pending: { label: '处理中', tone: 'warning' },
  processing: { label: '处理中', tone: 'warning' },
  failed: { label: '失败', tone: 'danger' },
  closed: { label: '已关闭', tone: 'danger' },
  cancelled: { label: '已取消', tone: 'danger' }
}

function transactionView(raw) {
  const item = raw || {}
  const type = String(item.type || '').toLowerCase()
  const presentation = TYPE_PRESENTATION[type] || {
    label: '账户变动', icon: '账', sign: '', tone: 'info'
  }
  const status = STATUS_PRESENTATION[String(item.status || '').toLowerCase()] || {
    label: item.status ? String(item.status) : '状态待确认', tone: 'warning'
  }
  const amount = Math.abs(finiteNumber(item.amount))
  return Object.assign({}, item, {
    id: item.id,
    title: item.description || presentation.label,
    iconText: presentation.icon,
    amountText: presentation.sign + '¥' + money(amount),
    amountTone: presentation.tone,
    statusText: status.label,
    statusTone: status.tone,
    timeText: dateTime(item.created_at),
    orderText: item.order_id ? ('订单 ' + item.order_id) : '',
    methodText: item.method === 'wechat' ? '微信' : (item.method === 'wallet' ? '钱包' : (item.method || '平台账户')),
    balanceText: item.balance_after === null || item.balance_after === undefined
      ? '待确认'
      : ('¥' + money(item.balance_after))
  })
}

function listFromPage(payload) {
  if (Array.isArray(payload)) return payload
  return payload && Array.isArray(payload.list) ? payload.list : []
}

function safePositiveId(value) {
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 0
}

function unavailable(message) {
  wx.showModal({
    title: '功能暂未开放',
    content: message || '该服务尚未接入可验证的生产接口，本次未执行任何变更。',
    showCancel: false
  })
}

module.exports = {
  finiteNumber,
  money,
  dateTime,
  transactionView,
  listFromPage,
  safePositiveId,
  unavailable
}

const app = getApp()
const { createRuntimePage, displayTime, listFrom, messageOf } = require('../../utils/detail-page')

const TYPE_TEXT = { order: '订单通知', system: '系统消息', activity: '活动消息' }
const FALLBACK_ROUTES = {
  client_orders: '/pages/client-orders/index',
  worker_orders: '/pages/worker-orders/index',
  client_notification: '/pages/client-notification/index',
  client_member: '/pages/client-member/index',
  client_coupon: '/pages/client-coupon/index',
  client_wallet: '/pages/client-wallet/index',
  worker_wallet: '/pages/worker-wallet/index',
  worker_profile: '/pages/worker-profile/index',
  client_quote_list: '/pages/client-quote-list/index',
  client_payment: '/pages/client-payment/index',
  worker_transactions: '/pages/worker-transactions/index'
}

function safePayload(value) {
  if (!value) return {}
  if (typeof value === 'object' && !Array.isArray(value)) return value
  if (typeof value !== 'string') return {}
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch (error) {
    return {}
  }
}

function withQuery(route, key, value) {
  if (!route || !key || !value) return route
  return route + (route.indexOf('?') >= 0 ? '&' : '?') + key + '=' + encodeURIComponent(value)
}

function resolveMessageTarget(payload) {
  const role = String(payload.role || 'user')
  const objectType = String(payload.object_type || payload.objectType || '')
  const objectId = String(
    payload.object_id ||
    payload.objectId ||
    payload.order_id ||
    payload.orderId ||
    payload.tx_id ||
    payload.txId ||
    payload.coupon_id ||
    payload.couponId ||
    ''
  )
  const fallback = String(payload.fallback_route || payload.fallbackRoute || '')

  if (objectType === 'order' && objectId) {
    if (fallback === 'client_quote_list') {
      return { route: withQuery('/pages/client-quote-list/index', 'orderId', objectId), label: '查看报价' }
    }
    if (fallback === 'client_payment') {
      return { route: withQuery('/pages/client-payment/index', 'orderId', objectId), label: '去支付' }
    }
    if (role === 'worker') {
      return { route: withQuery('/pages/order-detail-worker/index', 'id', objectId), label: '查看师傅订单' }
    }
    return { route: withQuery('/pages/order-detail-client/index', 'id', objectId), label: '查看相关订单' }
  }

  if (objectType === 'coupon' && objectId) {
    return { route: withQuery('/pages/client-coupon-detail/index', 'couponId', objectId), label: '查看优惠券' }
  }

  if (objectType === 'transaction' && objectId) {
    if (role === 'worker') return { route: '/pages/worker-transactions/index', label: '查看资金流水' }
    return { route: withQuery('/pages/client-transaction-detail/index', 'txId', objectId), label: '查看交易' }
  }

  const fallbackRoute = FALLBACK_ROUTES[fallback]
  return fallbackRoute ? { route: fallbackRoute, label: '前往处理' } : { route: '', label: '' }
}

Page(createRuntimePage({
  pageId: 'page-client-message-detail', route: 'pages/client-message-detail/index',
  source: 'pages/client-message-detail.html', sourceHash: 'fnv1a-a2b6bf5f', title: '消息详情'
}, {
  data: { loading: true, loadError: '', message: null, targetRoute: '', targetLabel: '' },
  onLoad(query) { this.messageId = String(query && (query.id || query.messageId) || ''); this.loadMessage() },
  async loadMessage() {
    if (!this.messageId) { this.setData({ loading: false, loadError: '缺少消息标识' }); return }
    this.setData({ loading: true, loadError: '' })
    try {
      const result = await app.getApi().messages.list({ page: 1, size: 100 })
      const raw = listFrom(result).find(item => String(item.id) === this.messageId)
      if (!raw) throw new Error('消息不存在或已被删除')
      const payload = safePayload(raw.payload)
      const target = resolveMessageTarget(payload)
      let isRead = !!raw.is_read
      if (!isRead && !target.route) {
        try {
          await app.getApi().messages.markRead(raw.id)
          isRead = true
        } catch (error) {
          console.warn('[消息已读标记失败]', error)
        }
      }
      this.setData({
        loading: false,
        targetRoute: target.route,
        targetLabel: target.label,
        message: Object.assign({}, raw, {
          payload,
          typeText: TYPE_TEXT[raw.type] || '消息',
          createdText: displayTime(raw.created_at, true),
          is_read: isRead
        })
      })
    } catch (error) { this.setData({ loading: false, loadError: messageOf(error), message: null }) }
  },
  async markCurrentRead() {
    const message = this.data.message
    if (!message || message.is_read) return
    try {
      await app.getApi().messages.markRead(message.id)
      this.setData({ 'message.is_read': true })
    } catch (error) {
      console.warn('[消息已读标记失败]', error)
    }
  },
  onOpenTarget() {
    if (!this.data.targetRoute) return
    wx.navigateTo({
      url: this.data.targetRoute,
      success: () => { this.markCurrentRead() },
      fail: () => wx.showToast({ title: '目标页面暂不可用', icon: 'none' })
    })
  },
  async onDelete() {
    if (!this.data.message) return
    const confirmed = await new Promise(resolve => wx.showModal({ title: '删除消息', content: '删除后无法恢复。', confirmColor: '#C4533A', success: result => resolve(result.confirm), fail: () => resolve(false) }))
    if (!confirmed) return
    try {
      await app.getApi().messages.remove(this.data.message.id)
      wx.showToast({ title: '已删除', icon: 'success' })
      setTimeout(() => wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-notification/index' }) }), 400)
    } catch (error) { wx.showToast({ title: messageOf(error, '删除失败'), icon: 'none' }) }
  }
}))

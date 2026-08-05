const { createBusinessPage } = require('../../utils/design-business-page')
const { money, safePositiveId } = require('../../utils/client-finance')

const DESIGN_META = Object.freeze({
  pageId: 'page-client-refund',
  route: 'pages/client-refund/index',
  source: 'pages/client-refund.html',
  sourceHash: 'fnv1a-3ca9cd50',
  title: '申请退款'
})

Page(createBusinessPage(DESIGN_META, {
  data: {
    loading: true, orderId: 0, order: null, loadError: '', refundType: 'full',
    reason: '服务质量问题', amount: '', note: '', submitting: false
  },

  onLoad(options) {
    const orderId = safePositiveId(options && (options.orderId || options.id))
    this.setData({ orderId })
    this.loadOrder()
  },

  async loadOrder() {
    if (!this.data.orderId) {
      this.setData({ loading: false, loadError: '未提供可核验的订单编号' })
      return
    }
    try {
      const raw = await getApp().getApi().orders.detail(this.data.orderId)
      const amount = Number(raw && (raw.final_price === null || raw.final_price === undefined ? raw.budget : raw.final_price)) || 0
      this.setData({
        loading: false,
        order: {
          id: raw.id,
          orderNo: raw.order_no,
          serviceName: raw.service_name || '平台维修服务',
          status: raw.status,
          statusText: String(raw.status || ''),
          amount,
          amountText: money(amount)
        },
        amount: amount ? amount.toFixed(2) : '',
        loadError: ''
      })
    } catch (error) {
      this.setData({ loading: false, order: null, loadError: error.message || '订单加载失败' })
    }
  },

  onType(event) {
    const type = event.currentTarget.dataset.type
    const next = type === 'partial' ? 'partial' : 'full'
    this.setData({ refundType: next, amount: next === 'full' && this.data.order ? this.data.order.amount.toFixed(2) : '' })
  },

  onReason(event) {
    this.setData({ reason: String(event.currentTarget.dataset.reason || '') })
  },

  onAmount(event) {
    this.setData({ amount: String(event.detail.value || '').replace(/[^0-9.]/g, '') })
  },

  onNote(event) {
    this.setData({ note: String(event.detail.value || '').slice(0, 500) })
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-orders/index' }) })
  },

  async onSubmit() {
    if (this.data.submitting || !this.data.order) return
    const allowedStatuses = ['completed', 'paid', 'pending_review', 'reviewed']
    if (!allowedStatuses.includes(this.data.order.status)) {
      wx.showToast({ title: '当前订单状态不支持提交退款审核', icon: 'none' })
      return
    }
    const amount = Number(this.data.amount)
    if (!Number.isFinite(amount) || amount <= 0 || amount > this.data.order.amount) {
      wx.showToast({ title: '退款金额必须大于 0 且不超过订单金额', icon: 'none' })
      return
    }
    const confirmed = await new Promise(resolve => wx.showModal({
      title: '提交退款审核工单',
      content: '提交后仅创建平台审核工单，不会立即退款或变更资金。是否继续？',
      success: result => resolve(result.confirm === true), fail: () => resolve(false)
    }))
    if (!confirmed) return

    this.setData({ submitting: true })
    try {
      const description = [
        '退款类型：' + (this.data.refundType === 'full' ? '全额退款' : '部分退款'),
        '申请金额：¥' + money(amount),
        '申请原因：' + this.data.reason,
        '补充说明：' + (this.data.note || '无')
      ].join('\n')
      const ticket = await getApp().getApi().ticket.create({
        ticket_type: 'refund_review',
        title: '订单 ' + this.data.order.orderNo + ' 退款审核',
        description,
        related_order_id: this.data.order.id,
        evidence_urls: []
      })
      if (!ticket || !ticket.id) throw new Error('服务端未返回工单编号')
      wx.redirectTo({ url: '/pages/client-customer-service/index?ticketId=' + encodeURIComponent(String(ticket.id)) })
    } catch (error) {
      wx.showToast({ title: error.message || '退款审核工单提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  }
}))

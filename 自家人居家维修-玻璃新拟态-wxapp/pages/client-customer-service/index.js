const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const STATUS_TEXT = {
  open: '待客服受理',
  pending: '待客服受理',
  processing: '处理中',
  resolved: '已解决',
  closed: '已关闭'
}

Page({
  data: {
    ticketId: '',
    relatedOrderId: '',
    ticket: null,
    order: null,
    messages: [],
    inputValue: '',
    loading: false,
    sending: false,
    loadError: false,
    statusText: '新建工单 · 尚未提交',
    scrollIntoView: '',
    icons: {}
  },

  onLoad(query) {
    this.setData({
      ticketId: query && query.ticketId ? String(query.ticketId) : '',
      relatedOrderId: query && (query.orderId || query.relatedOrderId) ? String(query.orderId || query.relatedOrderId) : '',
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        more: buildIcon('menu', COLORS.text1),
        send: buildIcon('navigation', COLORS.white),
        plus: buildIcon('plus', COLORS.text2),
        message: buildIcon('message', COLORS.white),
        arrow: buildIcon('chevronRight', COLORS.text3)
      }
    })
    if (this.data.ticketId) this.loadTicket()
    if (this.data.relatedOrderId) this.loadOrder()
  },

  formatTime(value) {
    if (!value) return ''
    const source = String(value)
    const date = new Date(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(source) ? source + 'Z' : source)
    if (Number.isNaN(date.getTime())) return ''
    const pad = n => String(n).padStart(2, '0')
    return pad(date.getHours()) + ':' + pad(date.getMinutes())
  },

  buildMessages(ticket) {
    if (!ticket) return []
    const result = []
    if (ticket.description) {
      result.push({ id: 'initial', role: 'user', name: '我', content: ticket.description, time: this.formatTime(ticket.created_at) })
    }
    ;(Array.isArray(ticket.replies) ? ticket.replies : []).forEach(reply => {
      const service = reply.reply_type === 'admin'
      result.push({
        id: 'reply-' + reply.id,
        role: service ? 'service' : 'user',
        name: service ? '客' : '我',
        content: reply.content,
        time: this.formatTime(reply.created_at)
      })
    })
    return result
  },

  async loadTicket() {
    this.setData({ loading: true, loadError: false })
    try {
      const ticket = await app.getApi().ticket.detail(this.data.ticketId)
      const messages = this.buildMessages(ticket)
      this.setData({
        ticket,
        messages,
        relatedOrderId: this.data.relatedOrderId || String(ticket.related_order_id || ''),
        statusText: STATUS_TEXT[ticket.status] || ticket.status || '状态待确认',
        loading: false,
        scrollIntoView: messages.length ? 'message-' + (messages.length - 1) : ''
      })
      if (!this.data.order && this.data.relatedOrderId) this.loadOrder()
    } catch (error) {
      console.error('加载客服工单失败', error)
      this.setData({ loading: false, loadError: true })
    }
  },

  async loadOrder() {
    const id = Number(this.data.relatedOrderId)
    if (!id) return
    try {
      const order = await app.getApi().orders.detail(id)
      this.setData({ order })
    } catch (error) {
      console.warn('关联订单暂不可用', error)
    }
  },

  onInput(e) {
    this.setData({ inputValue: String(e.detail.value || '').slice(0, 2000) })
  },

  onQuickReply(e) {
    this.setData({ inputValue: e.currentTarget.dataset.text || '' })
  },

  async onSend() {
    const content = String(this.data.inputValue || '').trim()
    if (!content) return
    if (this.data.sending) return
    if (this.data.ticket && ['resolved', 'closed'].indexOf(this.data.ticket.status) >= 0) {
      wx.showToast({ title: '该工单已结束，请新建工单', icon: 'none' })
      return
    }
    this.setData({ sending: true })
    try {
      const api = app.getApi()
      if (!this.data.ticketId) {
        if (content.length < 5) throw new Error('请至少输入5个字说明问题')
        const ticket = await api.ticket.create({
          ticket_type: this.data.relatedOrderId ? 'order_consult' : 'consult',
          title: content.slice(0, 30),
          description: content,
          related_order_id: this.data.relatedOrderId ? Number(this.data.relatedOrderId) : undefined,
          evidence_urls: []
        })
        this.setData({ ticketId: String(ticket.id), inputValue: '' })
      } else {
        await api.ticket.reply(this.data.ticketId, content)
        this.setData({ inputValue: '' })
      }
      await this.loadTicket()
    } catch (error) {
      console.error('提交客服消息失败', error)
      wx.showToast({ title: (error && error.message) || '提交失败', icon: 'none' })
    } finally {
      this.setData({ sending: false })
    }
  },

  onBack() { wx.navigateBack({ delta: 1 }) },
  onRetry() { this.loadTicket() },
  onMore() {
    wx.showActionSheet({
      itemList: ['查看我的工单'],
      success: () => wx.showToast({ title: '请从客服中心查看工单列表', icon: 'none' })
    })
  },
  onUnsupported() { wx.showToast({ title: '当前仅支持文字工单', icon: 'none' }) },
  onOrderTap() {
    if (this.data.relatedOrderId) wx.navigateTo({ url: '/pages/order-detail-client/index?orderId=' + this.data.relatedOrderId })
  }
})

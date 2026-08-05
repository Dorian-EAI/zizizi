const app = getApp()
const { createRuntimePage, displayTime, initial, messageOf } = require('../../utils/detail-page')

const TYPE_TEXT = { order: '订单问题', quality: '服务质量', refund: '退款问题', account: '账号问题', other: '其他问题' }
const STATUS_TEXT = { open: '待受理', pending: '待受理', processing: '处理中', resolved: '已解决', closed: '已关闭' }

function normalizeReply(raw) {
  const serviceReply = raw.reply_type === 'admin'
  return Object.assign({}, raw, {
    avatarText: initial(raw.replier_name, serviceReply ? '客' : '我'),
    displayName: serviceReply ? (raw.replier_name || '客服') : (raw.replier_name || '我'),
    createdText: displayTime(raw.created_at, true),
    serviceReply
  })
}

Page(createRuntimePage({
  pageId: 'page-client-ticket-detail',
  route: 'pages/client-ticket-detail/index',
  source: 'pages/client-ticket-detail.html',
  sourceHash: 'fnv1a-dd54b7dc',
  title: '工单详情'
}, {
  data: {
    loading: true,
    loadError: '',
    ticket: null,
    replies: [],
    evidenceUrls: [],
    replyText: '',
    sending: false,
    canReply: false
  },

  onLoad(query) {
    this.ticketId = String(query && (query.id || query.ticketId) || '')
    this.loadTicket()
  },

  async loadTicket() {
    if (!this.ticketId) {
      this.setData({ loading: false, loadError: '缺少工单标识', ticket: null })
      return
    }
    this.setData({ loading: true, loadError: '' })
    try {
      const raw = await app.getApi().ticket.detail(this.ticketId)
      const ticket = Object.assign({}, raw, {
        typeText: TYPE_TEXT[raw.ticket_type] || raw.ticket_type || '其他问题',
        statusText: STATUS_TEXT[raw.status] || raw.status || '状态未知',
        createdText: displayTime(raw.created_at, true),
        updatedText: displayTime(raw.updated_at, true),
        relatedOrderText: raw.related_order_id ? '#' + raw.related_order_id : '未关联订单',
        resolvedText: displayTime(raw.resolved_at, true)
      })
      this.setData({
        loading: false,
        ticket,
        replies: (Array.isArray(raw.replies) ? raw.replies : []).map(normalizeReply),
        evidenceUrls: Array.isArray(raw.evidence_urls) ? raw.evidence_urls : [],
        canReply: raw.status !== 'closed'
      })
    } catch (error) {
      this.setData({ loading: false, loadError: messageOf(error), ticket: null, replies: [], evidenceUrls: [], canReply: false })
    }
  },

  onReplyInput(event) {
    this.setData({ replyText: String(event.detail.value || '').slice(0, 2000) })
  },

  async onSend() {
    const content = String(this.data.replyText || '').trim()
    if (!this.data.canReply) {
      wx.showToast({ title: '工单已关闭，无法继续回复', icon: 'none' })
      return
    }
    if (!content) {
      wx.showToast({ title: '请输入回复内容', icon: 'none' })
      return
    }
    if (this.data.sending) return
    this.setData({ sending: true })
    try {
      await app.getApi().ticket.reply(this.ticketId, content)
      this.setData({ replyText: '' })
      wx.showToast({ title: '已发送', icon: 'success' })
      await this.loadTicket()
    } catch (error) {
      wx.showToast({ title: messageOf(error, '发送失败'), icon: 'none' })
    } finally {
      this.setData({ sending: false })
    }
  },

  onPreview(event) {
    const index = Number(event.currentTarget.dataset.index) || 0
    const urls = this.data.evidenceUrls
    if (urls[index]) wx.previewImage({ current: urls[index], urls })
  }
}))

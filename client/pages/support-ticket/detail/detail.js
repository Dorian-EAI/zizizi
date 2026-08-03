const api = require('../../../../utils/request')

const STATUS_MAP = {
  pending: '待处理',
  processing: '处理中',
  resolved: '已解决',
  closed: '已关闭'
}

const PRIORITY_MAP = {
  low: '低',
  medium: '中',
  high: '高'
}

Page({
  data: {
    ticket: null,
    messages: [],
    loading: true,
    replyText: ''
  },
  onLoad(options) {
    this.ticketId = options.id
    this.loadDetail()
  },
  loadDetail() {
    if (!this.ticketId) {
      this.setData({ loading: false })
      return
    }
    wx.showLoading({ title: '加载中...' })
    Promise.all([
      api.get(`/api/support-tickets/${this.ticketId}`).catch(() => null),
      api.get(`/api/support-tickets/${this.ticketId}/messages`).catch(() => [])
    ]).then(([ticket, msgs]) => {
      wx.hideLoading()
      const messages = Array.isArray(msgs) ? msgs : (msgs.list || [])
      if (ticket) {
        ticket.status_text = STATUS_MAP[ticket.status] || ticket.status
        ticket.priority_text = PRIORITY_MAP[ticket.priority] || ticket.priority
      }
      this.setData({ ticket, messages, loading: false })
    }).catch(() => {
      wx.hideLoading()
      this.setData({ loading: false })
    })
  },
  onReplyInput(e) {
    this.setData({ replyText: e.detail.value })
  },
  sendReply() {
    const text = (this.data.replyText || '').trim()
    if (!text) {
      wx.showToast({ title: '请输入回复内容', icon: 'none' })
      return
    }
    wx.showLoading({ title: '发送中...' })
    api.post(`/api/support-tickets/${this.ticketId}/messages`, { content: text }).then(() => {
      wx.hideLoading()
      this.setData({ replyText: '' })
      wx.showToast({ title: '发送成功', icon: 'success' })
      this.loadDetail()
    }).catch(() => {
      wx.hideLoading()
    })
  }
})

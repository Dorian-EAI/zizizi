// pages/client-service/index.js — 客服中心 玻璃新拟态（设计画布）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    servicePhoneDisplay: '暂未配置',
    servicePhoneConfigured: false,
    allTickets: [],
    tickets: [],
    faqItems: [],
    faqs: [],
    activePill: '全部',
    pills: ['全部', '进行中', '已解决'],
    orderId: '',
    submittingTicket: false,
    icons: {}
  },

  onLoad(query) {
    this._openCreateOnShow = query && query.create === '1'
    this.setData({
      orderId: query && query.orderId ? String(query.orderId) : '',
      statusBarHeight: app.globalData.statusBarHeight || 20,
      servicePhoneDisplay: app.globalData.servicePhone || '暂未配置',
      servicePhoneConfigured: !!String(app.globalData.servicePhone || '').trim(),
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        message: buildIcon('message', COLORS.brand),
        phone: buildIcon('phone', COLORS.accent),
        plus: buildIcon('plus', COLORS.brand),
        arrowRight: buildIcon('arrowRight', COLORS.brand)
      }
    })
    this.loadFaqs()
  },

  onShow() {
    this.loadTickets().then(loaded => {
      if (loaded && this._openCreateOnShow && !app.globalData._authRedirecting) {
        this._openCreateOnShow = false
        setTimeout(() => this.onNewTicket(), 100)
      }
    })
  },

  typeName(type) {
    const map = { complaint: '投诉', refund: '退款', claim: '理赔', consult: '咨询' }
    return map[type] || type
  },

  statusName(status) {
    const map = { processing: '处理中', reply: '待回复', resolved: '已解决', open: '待处理' }
    return map[status] || status
  },

  formatTicketTime(value) {
    if (!value) return ''
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return String(value)
    const pad = number => String(number).padStart(2, '0')
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) +
      ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
  },

  normalizeTicket(ticket) {
    const rawStatus = ticket.status || 'open'
    const status = rawStatus === 'resolved' || rawStatus === 'closed'
      ? 'resolved'
      : (rawStatus === 'waiting_user' || rawStatus === 'reply' ? 'reply' : 'processing')
    const type = ticket.ticket_type || ticket.type || 'consult'
    return Object.assign({}, ticket, {
      id: ticket.id,
      ticketNo: ticket.ticket_no || ticket.ticketNo || ticket.id,
      type,
      typeLabel: this.typeName(type),
      status,
      statusLabel: this.statusName(status),
      time: this.formatTicketTime(ticket.updated_at || ticket.created_at || ticket.time)
    })
  },

  async loadTickets() {
    const api = app.getApi()
    try {
      const result = await api.ticket.mine()
      const source = Array.isArray(result) ? result : ((result && result.items) || [])
      const allTickets = source.map(item => this.normalizeTicket(item))
      this.setData({ allTickets }, () => this.applyTicketFilter())
      return true
    } catch (error) {
      console.error('加载客服工单失败', error)
      this.setData({ allTickets: [], tickets: [] })
      return false
    }
  },

  async loadFaqs() {
    const api = app.getApi()
    try {
      const categories = await api.pages.faqs()
      const faqItems = []
      ;(Array.isArray(categories) ? categories : []).forEach(category => {
        ;(Array.isArray(category.faqs) ? category.faqs : []).forEach(item => {
          if (item && item.question && item.answer) faqItems.push(item)
        })
      })
      const visible = faqItems.slice(0, 5)
      this.setData({ faqItems: visible, faqs: visible.map(item => item.question) })
    } catch (error) {
      console.error('加载常见问题失败', error)
      this.setData({ faqItems: [], faqs: [] })
    }
  },

  applyTicketFilter() {
    const { activePill, allTickets } = this.data
    let tickets = allTickets
    if (activePill === '进行中') tickets = allTickets.filter(item => item.status !== 'resolved')
    if (activePill === '已解决') tickets = allTickets.filter(item => item.status === 'resolved')
    this.setData({ tickets })
  },

  onPillTap(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ activePill: key }, () => this.applyTicketFilter())
  },

  async onTicketTap(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/client-customer-service/index?ticketId=' + id })
  },

  onFaqTap(e) {
    const idx = e.currentTarget.dataset.idx
    const faq = this.data.faqItems[idx]
    if (!faq) return
    wx.showModal({
      title: faq.question,
      content: faq.answer,
      showCancel: false,
      confirmColor: '#0D9488'
    })
  },

  onOnlineService() {
    const suffix = this.data.orderId ? ('?orderId=' + this.data.orderId) : ''
    wx.navigateTo({ url: '/pages/client-customer-service/index' + suffix })
  },

  onCallHotline() {
    const phone = String(app.globalData.servicePhone || '').replace(/[^\d]/g, '')
    if (!phone) {
      wx.showToast({ title: '客服电话暂未配置', icon: 'none' })
      return
    }
    wx.makePhoneCall({
      phoneNumber: phone,
      fail: () => wx.showToast({ title: '呼叫失败，请稍后重试', icon: 'none' })
    })
  },

  onNewTicket() {
    if (this.data.submittingTicket) return
    const labels = ['服务投诉', '退款/费用', '保险理赔', '其他咨询']
    const types = ['complaint', 'refund', 'claim', 'consult']
    wx.showActionSheet({
      itemList: labels,
      success: result => this.openTicketPrompt(types[result.tapIndex], labels[result.tapIndex])
    })
  },

  promptDescription(title) {
    return new Promise(resolve => {
      wx.showModal({
        title,
        editable: true,
        placeholderText: '请描述问题及您的处理诉求',
        confirmText: '提交',
        confirmColor: '#0D9488',
        success: result => resolve(result.confirm ? String(result.content || '').trim() : '')
      })
    })
  },

  async openTicketPrompt(type, typeLabel) {
    if (this.data.submittingTicket) return
    const description = await this.promptDescription(typeLabel)
    if (!description) return
    if (description.length < 5) {
      wx.showToast({ title: '请至少填写5个字', icon: 'none' })
      return
    }

    this.setData({ submittingTicket: true })
    wx.showLoading({ title: '提交中', mask: true })
    try {
      const api = app.getApi()
      const numericOrderId = /^\d+$/.test(this.data.orderId) ? Number(this.data.orderId) : null
      await api.ticket.create({
        ticket_type: type,
        title: typeLabel + '：' + description.slice(0, 24),
        description,
        related_order_id: numericOrderId,
        evidence_urls: []
      })
      wx.hideLoading()
      wx.showToast({ title: '工单已提交', icon: 'success' })
      await this.loadTickets()
    } catch (error) {
      wx.hideLoading()
      console.error('提交客服工单失败', error)
    } finally {
      this.setData({ submittingTicket: false })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-mine/index' }) })
  }
})

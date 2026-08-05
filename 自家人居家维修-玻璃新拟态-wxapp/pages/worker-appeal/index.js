// pages/worker-appeal/index.js — 师傅申诉页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const APPEAL_TYPES = [
  { key: 'deduct', name: '扣除保证金' },
  { key: 'limit', name: '限制抢单' },
  { key: 'freeze', name: '账号冻结' },
  { key: 'other', name: '其他' }
]

const MAX_IMAGES = 5
const LEGACY_APPEAL_TYPE_KEYS = ['deduct', 'limit', 'freeze']

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = number => String(number).padStart(2, '0')
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) +
    ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
}

function getUploadedImageUrl(uploaded) {
  const raw = uploaded && (uploaded.url || (uploaded.data && uploaded.data.url))
  if (typeof raw !== 'string') return ''
  const url = raw.trim()
  if (/^\/uploads\//.test(url)) return url
  if (/^https?:\/\//i.test(url) && !/^https?:\/\/tmp\//i.test(url)) return url
  return ''
}

Page({
  data: {
    statusBarHeight: 20,
    appealTypes: APPEAL_TYPES,
    activeType: '',
    orderId: '',
    content: '',
    images: [],
    appeals: [],
    appealsLoading: true,
    submitting: false,
    maxImages: MAX_IMAGES,
    icons: {}
  },

  onLoad(query) {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      orderId: query && query.orderId ? String(query.orderId) : '',
      icons: {
        back: buildIcon('chevronLeft', COLORS.brandWorker),
        scale: buildIcon('scale', COLORS.brandWorker),
        plus: buildIcon('plus', COLORS.text3),
        chevronRight: buildIcon('chevronRight', COLORS.brandWorker),
        send: buildIcon('send', COLORS.white)
      }
    })
    this.loadAppeals()
  },

  onShow() {
    if (this._loadedOnce) this.loadAppeals()
    this._loadedOnce = true
  },

  normalizeAppeal(ticket) {
    const rawStatus = String(ticket.status || 'open')
    const statusMap = {
      open: { text: '待处理', tone: 'pending' },
      processing: { text: '处理中', tone: 'pending' },
      waiting_user: { text: '待补充', tone: 'pending' },
      resolved: { text: '已处理', tone: 'passed' },
      closed: { text: '已关闭', tone: 'rejected' }
    }
    const status = statusMap[rawStatus] || { text: rawStatus || '状态未知', tone: 'pending' }
    const legacyType = APPEAL_TYPES.find(item => item.key === ticket.ticket_type)
    const title = ticket.title || '申诉工单'
    return {
      id: ticket.id,
      typeLabel: legacyType ? legacyType.name : (title.replace(/申诉.*$/, '') || '申诉'),
      title,
      reason: ticket.related_order_id ? ('关联订单 #' + ticket.related_order_id) : (ticket.description || '暂无说明'),
      time: formatTime(ticket.updated_at || ticket.created_at),
      statusText: status.text,
      statusTone: status.tone
    }
  },

  async loadAppeals() {
    const api = app.getApi()
    this.setData({ appealsLoading: true })
    try {
      const result = await api.ticket.mine()
      const source = Array.isArray(result) ? result : ((result && result.items) || [])
      const appeals = source
        .filter(item => item && (
          item.ticket_type === 'appeal' ||
          LEGACY_APPEAL_TYPE_KEYS.indexOf(item.ticket_type) >= 0 ||
          (item.ticket_type === 'other' && /申诉/.test(item.title || ''))
        ))
        .map(item => this.normalizeAppeal(item))
      this.setData({ appeals })
    } catch (e) {
      console.error('加载申诉记录失败', e)
      this.setData({ appeals: [] })
    } finally {
      this.setData({ appealsLoading: false })
    }
  },

  async onAppealTap(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    const api = app.getApi()
    wx.showLoading({ title: '加载中', mask: true })
    try {
      const ticket = await api.ticket.detail(id)
      wx.hideLoading()
      const content = [
        ticket.description || '',
        ticket.resolution ? ('处理结果：' + ticket.resolution) : ''
      ].filter(Boolean).join('\n\n')
      wx.showModal({
        title: ticket.title || '申诉详情',
        content: content || '暂无更多详情',
        showCancel: false,
        confirmColor: '#2D6CDF'
      })
    } catch (error) {
      wx.hideLoading()
      console.error('加载申诉详情失败', error)
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onTypeTap(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ activeType: key })
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  async chooseImage() {
    const api = app.getApi()
    const cur = this.data.images
    if (cur.length >= MAX_IMAGES) return
    try {
      const res = await new Promise((resolve, reject) => {
        wx.chooseMedia({
          count: MAX_IMAGES - cur.length,
          mediaType: ['image'],
          sizeType: ['compressed'],
          success: resolve,
          fail: reject
        })
      })
      wx.showLoading({ title: '上传中' })
      const urls = []
      for (const f of res.tempFiles) {
        const uploaded = await api.upload.image(f.tempFilePath)
        const url = getUploadedImageUrl(uploaded)
        if (!url) throw new Error('图片上传结果无有效地址')
        urls.push(url)
      }
      wx.hideLoading()
      this.setData({ images: cur.concat(urls) })
    } catch (e) {
      wx.hideLoading()
      if (e && e.errMsg && e.errMsg.indexOf('cancel') >= 0) return
      console.error('上传失败', e)
      wx.showToast({ title: '上传失败', icon: 'none' })
    }
  },

  removeImage(e) {
    const idx = e.currentTarget.dataset.idx
    const arr = this.data.images.slice()
    arr.splice(idx, 1)
    this.setData({ images: arr })
  },

  async onSubmit() {
    if (this.data.submitting) return
    if (!this.data.activeType) {
      wx.showToast({ title: '请选择申诉类型', icon: 'none' })
      return
    }
    if (!this.data.content.trim()) {
      wx.showToast({ title: '请填写申诉内容', icon: 'none' })
      return
    }
    if (this.data.orderId && !/^\d+$/.test(this.data.orderId)) {
      wx.showToast({ title: '关联订单ID应为数字', icon: 'none' })
      return
    }
    const api = app.getApi()
    this.setData({ submitting: true })
    try {
      // 后端 CreateTicketRequest 字段：ticket_type / title / description / related_order_id / evidence_urls
      const appealName = (APPEAL_TYPES.find(t => t.key === this.data.activeType) || {}).name || '申诉'
      await api.ticket.create({
        ticket_type: 'appeal',
        title: appealName + '申诉',
        description: '申诉类型：' + appealName + '\n' + this.data.content.trim(),
        related_order_id: this.data.orderId ? Number(this.data.orderId) : null,
        evidence_urls: this.data.images
      })
      wx.showToast({ title: '提交成功', icon: 'success' })
      this.setData({ activeType: '', content: '', images: [] })
      await this.loadAppeals()
    } catch (e) {
      console.error('提交申诉失败', e)
      wx.showToast({ title: '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  }
})

const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const TYPES = ['服务态度问题', '未按约定到达', '收费争议', '技术或质量问题', '疑似骚扰', '其他']
const MAX_IMAGES = 9

function uploadedUrl(result) {
  const raw = typeof result === 'string' ? result : result && (result.url || (result.data && result.data.url))
  if (typeof raw !== 'string') return ''
  const value = raw.trim()
  if (/^\/uploads\//.test(value)) return value
  if (/^https?:\/\//i.test(value) && !/^https?:\/\/tmp\//i.test(value)) return value
  return ''
}

Page({
  data: {
    workerId: '',
    orderId: '',
    worker: null,
    types: TYPES,
    selectedType: '',
    content: '',
    images: [],
    submitting: false,
    maxImages: MAX_IMAGES,
    icons: {
      back: buildIcon('arrowLeft', COLORS.text1),
      user: buildIcon('user', COLORS.brand),
      camera: buildIcon('camera', COLORS.brand)
    }
  },

  onLoad(query) {
    this.setData({
      workerId: String(query && query.workerId || ''),
      orderId: String(query && query.orderId || '')
    })
    this.loadWorker()
  },

  async loadWorker() {
    if (!/^\d+$/.test(this.data.workerId)) return
    try {
      const worker = await app.getApi().services.workerDetail(this.data.workerId)
      this.setData({ worker })
    } catch (error) {
      console.warn('投诉对象公开资料不可用', error)
    }
  },

  onType(e) { this.setData({ selectedType: e.currentTarget.dataset.type }) },
  onInput(e) { this.setData({ content: String(e.detail.value || '').slice(0, 500) }) },

  async chooseImage() {
    const remaining = MAX_IMAGES - this.data.images.length
    if (remaining <= 0) return
    try {
      const result = await new Promise((resolve, reject) => wx.chooseMedia({
        count: remaining,
        mediaType: ['image'],
        sizeType: ['compressed'],
        success: resolve,
        fail: reject
      }))
      const files = (result.tempFiles || []).map(item => item.tempFilePath).filter(Boolean)
      this.setData({ images: this.data.images.concat(files).slice(0, MAX_IMAGES) })
    } catch (error) {
      if (!error || !/cancel/i.test(error.errMsg || '')) console.warn('选择证据图片失败', error)
    }
  },

  removeImage(e) {
    const index = Number(e.currentTarget.dataset.index)
    this.setData({ images: this.data.images.filter((_, itemIndex) => itemIndex !== index) })
  },

  async uploadEvidence() {
    const api = app.getApi()
    const urls = []
    for (let index = 0; index < this.data.images.length; index += 1) {
      const result = await api.upload.image(this.data.images[index])
      const url = uploadedUrl(result)
      if (!url) throw new Error('第' + (index + 1) + '张证据上传失败')
      urls.push(url)
    }
    return urls
  },

  async onSubmit() {
    if (this.data.submitting) return
    const content = this.data.content.trim()
    if (!this.data.selectedType) {
      wx.showToast({ title: '请选择投诉类型', icon: 'none' })
      return
    }
    if (content.length < 5) {
      wx.showToast({ title: '请至少填写5个字', icon: 'none' })
      return
    }
    if (this.data.orderId && !/^\d+$/.test(this.data.orderId)) {
      wx.showToast({ title: '关联订单标识无效', icon: 'none' })
      return
    }
    const confirmed = await new Promise(resolve => wx.showModal({
      title: '确认提交投诉',
      content: '平台将按工单流程核实，处理状态以服务端记录为准。',
      confirmText: '确认提交',
      success: result => resolve(result.confirm),
      fail: () => resolve(false)
    }))
    if (!confirmed) return

    this.setData({ submitting: true })
    wx.showLoading({ title: '正在提交', mask: true })
    try {
      const evidenceUrls = await this.uploadEvidence()
      const workerLine = this.data.workerId ? ('投诉对象师傅ID：' + this.data.workerId + '\n') : ''
      const ticket = await app.getApi().ticket.create({
        ticket_type: 'complaint',
        title: this.data.selectedType,
        description: workerLine + '投诉类型：' + this.data.selectedType + '\n' + content,
        related_order_id: this.data.orderId ? Number(this.data.orderId) : undefined,
        evidence_urls: evidenceUrls
      })
      if (!ticket || !ticket.id) throw new Error('服务端未返回投诉工单编号')
      wx.hideLoading()
      wx.redirectTo({ url: '/pages/client-ticket-detail/index?ticketId=' + encodeURIComponent(ticket.id) })
    } catch (error) {
      wx.hideLoading()
      console.error('提交投诉失败', error)
      wx.showToast({ title: (error && error.message) || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  onSupport() {
    wx.navigateTo({ url: '/pages/client-customer-service/index' + (this.data.orderId ? ('?orderId=' + encodeURIComponent(this.data.orderId)) : '') })
  },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

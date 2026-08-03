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
    submitting: false,
    maxImages: MAX_IMAGES,
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.brandWorker),
        scale: buildIcon('scale', COLORS.brandWorker),
        plus: buildIcon('plus', COLORS.text3),
        chevronRight: buildIcon('chevronRight', COLORS.brandWorker),
        send: buildIcon('send', COLORS.white)
      }
    })
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
    const api = app.getApi()
    this.setData({ submitting: true })
    try {
      // 后端 CreateTicketRequest 字段：ticket_type / title / description / related_order_id / evidence_urls
      const appealName = (APPEAL_TYPES.find(t => t.key === this.data.activeType) || {}).name || '申诉'
      await api.ticket.create({
        ticket_type: this.data.activeType,
        title: appealName + '申诉',
        description: this.data.content,
        related_order_id: this.data.orderId ? Number(this.data.orderId) : null,
        evidence_urls: this.data.images
      })
      wx.showToast({ title: '提交成功', icon: 'success' })
      setTimeout(() => wx.navigateBack({ delta: 1 }), 800)
    } catch (e) {
      console.error('提交申诉失败', e)
      wx.showToast({ title: '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  }
})

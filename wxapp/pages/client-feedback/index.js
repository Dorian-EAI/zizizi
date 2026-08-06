// pages/client-feedback/index.js — 意见反馈 玻璃新拟态
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const MAX_IMAGES = 3
const MAX_CONTENT = 500

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
    types: [
      { key: 'suggestion', name: '功能建议' },
      { key: 'bug',        name: 'Bug 反馈' },
      { key: 'complaint',  name: '服务投诉' },
      { key: 'other',      name: '其他' }
    ],
    selectedType: '',
    content: '',
    contentCount: 0,
    maxContent: MAX_CONTENT,
    phone: '',
    images: [],
    maxImages: MAX_IMAGES,
    submitting: false,
    history: [],
    expandedId: '',
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        plus: buildIcon('plus', COLORS.text3),
        phone: buildIcon('phone', COLORS.brand),
        chevronRight: buildIcon('chevronRight', COLORS.brand),
        close: buildIcon('x', COLORS.white),
        camera: buildIcon('camera', COLORS.brand),
        empty: buildIcon('message', COLORS.text3),
        arrowRight: buildIcon('arrowRight', COLORS.text3)
      }
    })
    this.loadHistory()
  },

  async loadHistory() {
    const api = app.getApi()
    try {
      const list = await api.feedback.mine({ page: 1, size: 20 })
      const raw = (list && list.items) || list || []
      // 后端返回 created_at(snake)，WXML 绑定 createdAt；补全 typeText/statusText
      const TYPE_TEXT = { suggestion: '功能建议', bug: 'Bug反馈', complaint: '服务投诉', other: '其他' }
      const STATUS_TEXT = { pending: '处理中', processing: '处理中', resolved: '已解决' }
      const history = raw.map(f => Object.assign({}, f, {
        createdAt: f.created_at != null ? f.created_at : f.createdAt,
        typeText: f.typeText || TYPE_TEXT[f.type] || f.type,
        statusText: f.statusText || STATUS_TEXT[f.status] || f.status
      }))
      this.setData({ history })
    } catch (e) {
      console.error('加载历史反馈失败', e)
    }
  },

  // 选择类型（互斥）
  onTypeTap(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ selectedType: key === this.data.selectedType ? '' : key })
  },

  onContentInput(e) {
    const value = e.detail.value || ''
    this.setData({
      content: value,
      contentCount: value.length
    })
  },

  onPhoneInput(e) {
    this.setData({ phone: e.detail.value || '' })
  },

  // 选择图片
  onChooseImage() {
    const remain = this.data.maxImages - this.data.images.length
    if (remain <= 0) {
      wx.showToast({ title: '最多上传 ' + this.data.maxImages + ' 张', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        const newPaths = (res.tempFiles || []).map(f => f.tempFilePath)
        const images = this.data.images.concat(newPaths).slice(0, this.data.maxImages)
        this.setData({ images })
      }
    })
  },

  onRemoveImage(e) {
    const idx = e.currentTarget.dataset.index
    const images = this.data.images.slice()
    images.splice(idx, 1)
    this.setData({ images })
  },

  // 预览图片
  onPreviewImage(e) {
    const current = e.currentTarget.dataset.src
    wx.previewImage({ current, urls: this.data.images })
  },

  // 展开 / 折叠历史
  onHistoryToggle(e) {
    const id = e.currentTarget.dataset.id
    this.setData({ expandedId: this.data.expandedId === id ? '' : id })
  },

  // 提交
  async onSubmit() {
    const { selectedType, content, phone, images } = this.data
    if (!selectedType) {
      wx.showToast({ title: '请选择反馈类型', icon: 'none' })
      return
    }
    if (!content.trim()) {
      wx.showToast({ title: '请填写反馈内容', icon: 'none' })
      return
    }
    if (this.data.submitting) return
    this.setData({ submitting: true })
    wx.showLoading({ title: '提交中', mask: true })
    try {
      const api = app.getApi()
      // 上传图片
      const imageUrls = []
      for (let i = 0; i < images.length; i++) {
        const up = await api.upload.image(images[i])
        const url = getUploadedImageUrl(up)
        if (!url) throw new Error('第' + (i + 1) + '张图片上传失败')
        imageUrls.push(url)
      }
      // 后端 FeedbackCreateRequest(extra=forbid) 字段为 contact，前端 phone 需重映射，否则 422
      await api.feedback.create({
        type: selectedType,
        content: content.trim(),
        contact: phone || '',
        images: imageUrls
      })
      wx.hideLoading()
      wx.showToast({ title: '提交成功', icon: 'success' })
      // 重置表单
      this.setData({
        selectedType: '',
        content: '',
        contentCount: 0,
        phone: '',
        images: []
      })
      // 刷新历史
      this.loadHistory()
    } catch (e) {
      wx.hideLoading()
      console.error('提交反馈失败', e)
      wx.showToast({ title: '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-mine/index' }) })
  }
})

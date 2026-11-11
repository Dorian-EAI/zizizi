const app = getApp()
const { createRuntimePage, messageOf } = require('../../utils/detail-page')

const TYPES = [
  { key: 'order', name: '订单问题' },
  { key: 'quality', name: '服务质量' },
  { key: 'refund', name: '退款问题' },
  { key: 'account', name: '账号问题' },
  { key: 'other', name: '其他' }
]

function uploadedUrl(result) {
  const value = result && (result.url || result.file_url || (result.data && (result.data.url || result.data.file_url)))
  return typeof value === 'string' ? value.trim() : ''
}

Page(createRuntimePage({
  pageId: 'page-client-ticket-submit',
  route: 'pages/client-ticket-submit/index',
  source: 'pages/client-ticket-submit.html',
  sourceHash: 'fnv1a-11a1e066',
  title: '提交工单'
}, {
  data: {
    types: TYPES,
    selectedType: 'order',
    title: '',
    description: '',
    descriptionLength: 0,
    relatedOrderId: '',
    relatedOrderText: '未关联订单',
    images: [],
    submitting: false,
    uploading: false
  },

  onLoad(query) {
    const orderId = query && (query.orderId || query.id)
    if (orderId) this.applyOrder({ id: orderId, order_no: query.orderNo, service_name: query.serviceName })
  },

  applyOrder(order) {
    if (!order || !order.id) return
    const details = [order.service_name, order.order_no ? '#' + order.order_no : '#' + order.id].filter(Boolean)
    this.setData({ relatedOrderId: String(order.id), relatedOrderText: details.join(' · ') || '#' + order.id })
  },

  onType(event) {
    this.setData({ selectedType: event.currentTarget.dataset.key || 'other' })
  },

  onTitleInput(event) {
    this.setData({ title: String(event.detail.value || '').slice(0, 200) })
  },

  onDescriptionInput(event) {
    const description = String(event.detail.value || '').slice(0, 5000)
    this.setData({ description, descriptionLength: description.length })
  },

  onOrderInput(event) {
    const value = String(event.detail.value || '').replace(/\D/g, '').slice(0, 20)
    this.setData({ relatedOrderId: value, relatedOrderText: value ? '#' + value : '未关联订单' })
  },

  onChooseOrder() {
    wx.navigateTo({
      url: '/package-client/pages/client-order-picker/index',
      events: { orderSelected: order => this.applyOrder(order) }
    })
  },

  async onChooseImages() {
    const remaining = 6 - this.data.images.length
    if (remaining <= 0) {
      wx.showToast({ title: '最多选择6张图片', icon: 'none' })
      return
    }
    try {
      let result
      if (wx.chooseMedia) {
        result = await new Promise((resolve, reject) => wx.chooseMedia({ count: remaining, mediaType: ['image'], sourceType: ['album', 'camera'], sizeType: ['compressed'], success: resolve, fail: reject }))
      } else {
        result = await new Promise((resolve, reject) => wx.chooseImage({ count: remaining, sourceType: ['album', 'camera'], sizeType: ['compressed'], success: resolve, fail: reject }))
      }
      const paths = (result.tempFiles || []).map(item => item.tempFilePath).concat(result.tempFilePaths || []).filter(Boolean)
      this.setData({ images: this.data.images.concat(paths).slice(0, 6) })
    } catch (error) {
      const text = String(error && (error.errMsg || error.message) || '')
      if (text.indexOf('cancel') < 0) wx.showToast({ title: '选择图片失败', icon: 'none' })
    }
  },

  onRemoveImage(event) {
    const index = Number(event.currentTarget.dataset.index)
    this.setData({ images: this.data.images.filter((_, position) => position !== index) })
  },

  onPreview(event) {
    const index = Number(event.currentTarget.dataset.index) || 0
    const urls = this.data.images
    if (urls[index]) wx.previewImage({ current: urls[index], urls })
  },

  async onSubmit() {
    const title = String(this.data.title || '').trim()
    const description = String(this.data.description || '').trim()
    if (title.length < 2) {
      wx.showToast({ title: '请填写工单标题', icon: 'none' })
      return
    }
    if (description.length < 5) {
      wx.showToast({ title: '请详细描述问题', icon: 'none' })
      return
    }
    if (this.data.submitting) return
    this.setData({ submitting: true, uploading: this.data.images.length > 0 })
    wx.showLoading({ title: this.data.images.length ? '上传凭证' : '提交工单', mask: true })
    try {
      const api = app.getApi()
      const evidenceUrls = []
      for (const filePath of this.data.images) {
        const url = uploadedUrl(await api.upload.image(filePath))
        if (!url) throw new Error('上传响应缺少文件地址')
        evidenceUrls.push(url)
      }
      const payload = {
        ticket_type: this.data.selectedType,
        title,
        description,
        evidence_urls: evidenceUrls
      }
      if (this.data.relatedOrderId) payload.related_order_id = Number(this.data.relatedOrderId)
      const ticket = await api.ticket.create(payload)
      if (!ticket || !ticket.id) throw new Error('服务端未返回工单标识')
      wx.hideLoading()
      wx.showToast({ title: '工单已提交', icon: 'success' })
      setTimeout(() => wx.redirectTo({ url: '/package-client/pages/client-ticket-detail/index?id=' + ticket.id }), 500)
    } catch (error) {
      wx.hideLoading()
      wx.showToast({ title: messageOf(error, '提交失败'), icon: 'none' })
    } finally {
      this.setData({ submitting: false, uploading: false })
    }
  }
}))

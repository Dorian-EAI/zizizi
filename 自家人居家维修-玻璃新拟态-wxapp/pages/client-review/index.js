const app = getApp()
const { buildIcon, buildFilledIcon, COLORS } = require('../../utils/icons')

const STAR_TEXT = ['', '很不满意', '不满意', '一般', '满意', '非常满意']
const TAGS = ['服务好', '准时到达', '技术专业', '干净整洁', '价格合理', '态度好', '响应快', '讲解细致']

Page({
  data: {
    orderId: '',
    order: null,
    loading: true,
    loadError: false,
    unavailableReason: '',
    canReview: false,
    rating: 0,
    starText: '请选择评分',
    tags: TAGS.map(name => ({ name, selected: false })),
    content: '',
    contentLength: 0,
    images: [],
    anonymous: true,
    uploading: false,
    submitting: false,
    icons: {}
  },

  onLoad(query) {
    this.setData({
      orderId: query && (query.orderId || query.id) ? String(query.orderId || query.id) : '',
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        star: buildIcon('star', COLORS.text3),
        starActive: buildFilledIcon('star', COLORS.accent),
        image: buildIcon('image', COLORS.text3),
        user: buildIcon('user', COLORS.brand)
      }
    })
    this.loadOrder()
  },

  derivePermission(order) {
    const actions = Array.isArray(order && order.allowed_actions) ? order.allowed_actions : []
    if (actions.indexOf('review_order') < 0) return '服务端未授权当前订单评价'
    return ''
  },

  async loadOrder() {
    if (!this.data.orderId) {
      this.setData({ loading: false, loadError: true, unavailableReason: '缺少订单标识' })
      return
    }
    this.setData({ loading: true, loadError: false })
    try {
      const order = await app.getApi().orders.detail(this.data.orderId)
      const reason = this.derivePermission(order)
      this.setData({ order, loading: false, canReview: !reason, unavailableReason: reason })
    } catch (error) {
      console.error('加载待评价订单失败', error)
      this.setData({ loading: false, loadError: true, unavailableReason: (error && error.message) || '订单加载失败' })
    }
  },

  onRate(e) {
    const rating = Number(e.currentTarget.dataset.value)
    if (rating >= 1 && rating <= 5) this.setData({ rating, starText: STAR_TEXT[rating] })
  },

  onTag(e) {
    const name = e.currentTarget.dataset.name
    this.setData({ tags: this.data.tags.map(item => item.name === name ? Object.assign({}, item, { selected: !item.selected }) : item) })
  },

  onContent(e) {
    const content = String(e.detail.value || '').slice(0, 500)
    this.setData({ content, contentLength: content.length })
  },

  onToggleAnonymous() { this.setData({ anonymous: !this.data.anonymous }) },

  async onChooseImages() {
    if (this.data.uploading) return
    const remaining = 9 - this.data.images.length
    if (remaining <= 0) {
      wx.showToast({ title: '最多上传9张图片', icon: 'none' })
      return
    }
    try {
      const result = await new Promise((resolve, reject) => wx.chooseMedia({ count: remaining, mediaType: ['image'], sourceType: ['album', 'camera'], success: resolve, fail: reject }))
      const files = (result.tempFiles || []).map(item => item.tempFilePath).filter(Boolean)
      if (!files.length) return
      this.setData({ uploading: true })
      wx.showLoading({ title: '上传图片', mask: true })
      const uploaded = []
      for (const localPath of files) {
        const response = await app.getApi().upload.image(localPath)
        const url = response && (response.url || response.file_url)
        if (!url) throw new Error('上传响应缺少文件地址')
        uploaded.push({ localPath, url })
      }
      wx.hideLoading()
      this.setData({ images: this.data.images.concat(uploaded), uploading: false })
    } catch (error) {
      wx.hideLoading()
      this.setData({ uploading: false })
      const message = String(error && (error.errMsg || error.message) || '')
      if (message.indexOf('cancel') < 0) wx.showToast({ title: (error && error.message) || '图片上传失败', icon: 'none' })
    }
  },

  onPreview(e) {
    const index = Number(e.currentTarget.dataset.index)
    const urls = this.data.images.map(item => item.localPath || item.url)
    wx.previewImage({ current: urls[index], urls })
  },

  onDeleteImage(e) {
    const index = Number(e.currentTarget.dataset.index)
    const images = this.data.images.filter((_, i) => i !== index)
    this.setData({ images })
    // 普通用户无权调用管理员对象删除接口。这里只移除本次评价选择；
    // 未提交的私有临时对象由服务端生命周期清理，避免 403 或越权删除。
  },

  async onSubmit() {
    if (!this.data.canReview) {
      wx.showToast({ title: this.data.unavailableReason || '当前不可评价', icon: 'none' })
      return
    }
    if (!this.data.rating) {
      wx.showToast({ title: '请选择评分', icon: 'none' })
      return
    }
    if (this.data.uploading || this.data.submitting) return
    this.setData({ submitting: true })
    wx.showLoading({ title: '提交评价', mask: true })
    try {
      const latest = await app.getApi().orders.detail(this.data.orderId)
      const reason = this.derivePermission(latest)
      if (reason) throw new Error(reason)
      await app.getApi().orders.review(this.data.orderId, {
        rating: this.data.rating,
        tags: this.data.tags.filter(item => item.selected).map(item => item.name),
        content: this.data.content || undefined,
        images: this.data.images.map(item => item.url),
        is_anonymous: this.data.anonymous
      })
      wx.hideLoading()
      wx.showToast({ title: '评价已提交', icon: 'success' })
      setTimeout(() => wx.redirectTo({ url: '/pages/order-detail-client/index?orderId=' + this.data.orderId }), 700)
    } catch (error) {
      wx.hideLoading()
      console.error('提交评价失败', error)
      wx.showToast({ title: (error && error.message) || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  onBack() { wx.navigateBack({ delta: 1 }) }
})

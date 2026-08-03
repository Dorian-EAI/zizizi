const api = require('../../../utils/request')

const STATUS_MAP = {
  pending: '待接单',
  accepted: '已接单',
  departing: '师傅出发',
  arrived: '师傅已到达',
  serving: '服务中',
  completed: '待支付',
  paid: '待评价',
  reviewed: '已完成',
  cancelled: '已取消'
}

const STATUS_DESC = {
  pending: '订单已提交，等待师傅报价',
  accepted: '师傅已接单，等待出发',
  departing: '师傅正在赶来，点击下方追踪实时位置',
  arrived: '师傅已到达服务地点',
  serving: '师傅正在提供服务',
  completed: '服务已完成，请确认支付',
  paid: '支付完成，请确认服务并评价',
  reviewed: '订单已完成，感谢您的评价',
  cancelled: '订单已取消'
}

const PAY_METHODS = [
  { value: 'wallet', label: '钱包余额' },
  { value: 'wechat', label: '微信支付' },
  { value: 'combined', label: '组合支付' },
  { value: 'offline', label: '线下支付' }
]

Page({
  data: {
    orderId: null,
    order: null,
    biddings: [],
    trackList: [],
    trackMarkers: [],
    trackPolyline: [],
    mapCenter: { latitude: 0, longitude: 0 },
    showReview: false,
    review: {
      rating: 5,
      tags: [],
      content: '',
      images: [],
      anonymous: false
    },
    presetTags: ['技术好', '准时', '收费合理', '态度好', '专业', '响应快', '经验丰富', '不满意', '迟到', '收费高'],
    showPayMethodSelector: false,
    showPaymentModal: false,
    payMethod: '',
    payMethods: PAY_METHODS,
    payForm: {
      wallet_amount: '',
      wechat_amount: '',
      coupon_id: null
    }
  },

  onLoad(options) {
    const id = options.id
    this.setData({ orderId: id })
    this.loadOrder(id)
    this.loadTrack(id)
  },

  loadOrder(id) {
    api.get(`/api/orders/${id}`).then(data => {
      data.status_text = STATUS_MAP[data.status] || data.status
      data.status_desc = STATUS_DESC[data.status] || ''
      data.images = this.parseImages(data.images)
      this.setData({ order: data })
      if (data.status === 'pending') {
        this.loadBiddings(id)
      }
    }).catch(() => wx.showToast({ title: '加载失败', icon: 'none' }))
  },

  loadBiddings(id) {
    api.get(`/api/orders/${id}/biddings`).then(data => {
      this.setData({ biddings: Array.isArray(data) ? data : [] })
    }).catch(() => wx.showToast({ title: '报价加载失败', icon: 'none' }))
  },

  loadTrack(id) {
    api.get(`/api/lbs-track/orders/${id}/track`).then(data => {
      const list = Array.isArray(data) ? data : []
      this.setData({ trackList: list })
      this.buildTrackMap(list)
    }).catch(() => {
      // 轨迹为非核心数据，失败不打扰用户
      this.setData({ trackList: [], trackMarkers: [], trackPolyline: [] })
    })
  },
  buildTrackMap(list) {
    if (!list || !list.length) {
      this.setData({ trackMarkers: [], trackPolyline: [], mapCenter: { latitude: 0, longitude: 0 } })
      return
    }
    const markers = []
    const points = []
    list.forEach((item, idx) => {
      const lat = item.latitude
      const lng = item.longitude
      if (lat == null || lng == null) return
      points.push({ latitude: lat, longitude: lng })
      markers.push({
        id: idx,
        latitude: lat,
        longitude: lng,
        iconPath: '/assets/marker.png',
        width: 28,
        height: 28,
        callout: {
          content: item.action || item.location || '位置更新',
          color: '#333',
          fontSize: 12,
          borderRadius: 8,
          bgColor: '#fff',
          padding: 6,
          display: 'ALWAYS'
        }
      })
    })
    let mapCenter = { latitude: 0, longitude: 0 }
    if (points.length) {
      const latSum = points.reduce((s, p) => s + p.latitude, 0)
      const lngSum = points.reduce((s, p) => s + p.longitude, 0)
      mapCenter = { latitude: latSum / points.length, longitude: lngSum / points.length }
    }
    const polyline = points.length > 1
      ? [{ points, color: '#004080', width: 6 }]
      : []
    this.setData({ trackMarkers: markers, trackPolyline: polyline, mapCenter })
  },
  openTrackNavigation(e) {
    const { latitude, longitude, name, address } = e.currentTarget.dataset
    if (!latitude || !longitude) {
      wx.showToast({ title: '该轨迹点无位置信息', icon: 'none' })
      return
    }
    wx.openLocation({
      latitude: parseFloat(latitude),
      longitude: parseFloat(longitude),
      name: name || '',
      address: address || '',
      scale: 18
    })
  },

  parseImages(images) {
    if (!images) return []
    if (Array.isArray(images)) return images
    if (typeof images === 'string') {
      try {
        const parsed = JSON.parse(images)
        return Array.isArray(parsed) ? parsed : []
      } catch (e) {
        return images ? [images] : []
      }
    }
    return []
  },

  cancelOrder() {
    wx.showModal({
      title: '取消订单',
      content: '确定取消该订单吗？',
      success: res => {
        if (res.confirm) {
          api.put(`/api/orders/${this.data.orderId}/status`, { status: 'cancelled' })
            .then(() => {
              wx.showToast({ title: '已取消' })
              this.loadOrder(this.data.orderId)
            })
            .catch(() => wx.showToast({ title: '取消失败', icon: 'none' }))
        }
      }
    })
  },

  goTracking() {
    wx.navigateTo({
      url: `/pages/order/tracking/tracking?order_id=${this.data.orderId}`
    })
  },

  selectWorker(e) {
    const biddingId = e.currentTarget.dataset.id
    wx.showModal({
      title: '选择师傅',
      content: '确定选择该师傅为您服务吗？',
      success: res => {
        if (res.confirm) {
          api.post(`/api/orders/${this.data.orderId}/select`, { bidding_id: biddingId })
            .then(() => {
              wx.showToast({ title: '选择成功' })
              this.loadOrder(this.data.orderId)
            })
            .catch(() => wx.showToast({ title: '选择失败', icon: 'none' }))
        }
      }
    })
  },

  completeOrder() {
    wx.showModal({
      title: '完成服务',
      editable: true,
      placeholderText: '请输入本次服务成交价',
      success: res => {
        if (res.confirm) {
          const price = parseFloat(res.content)
          if (!price || price <= 0) {
            wx.showToast({ title: '请输入有效金额', icon: 'none' })
            return
          }
          api.put(`/api/orders/${this.data.orderId}/status`, { status: 'completed', price })
            .then(() => {
              wx.showToast({ title: '提交成功' })
              this.loadOrder(this.data.orderId)
            })
            .catch(() => wx.showToast({ title: '提交失败', icon: 'none' }))
        }
      }
    })
  },

  openPayMethodSelector() {
    this.setData({ showPayMethodSelector: true })
  },

  closePayMethodSelector() {
    this.setData({ showPayMethodSelector: false })
  },

  onSelectPayMethod(e) {
    const method = e.currentTarget.dataset.method
    this.setData({ showPayMethodSelector: false })
    if (method === 'combined') {
      const finalPrice = this.data.order?.final_price || this.data.order?.total_amount || 0
      this.setData({
        payMethod: method,
        showPaymentModal: true,
        'payForm.wallet_amount': String(finalPrice),
        'payForm.wechat_amount': '0'
      })
    } else {
      this.payOrder(method)
    }
  },

  closePaymentModal() {
    this.setData({ showPaymentModal: false, payMethod: '' })
  },

  onPayInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [`payForm.${field}`]: e.detail.value })
  },

  payOrder(methodOrEvent) {
    let method = methodOrEvent
    if (methodOrEvent && typeof methodOrEvent === 'object' && methodOrEvent.currentTarget) {
      method = methodOrEvent.currentTarget.dataset.method
    }
    const orderNo = this.data.order?.order_no
    if (!orderNo) {
      wx.showToast({ title: '订单信息缺失', icon: 'none' })
      return
    }
    const payload = { order_no: orderNo, method }
    if (method === 'combined') {
      const wallet = parseFloat(this.data.payForm.wallet_amount) || 0
      const wechat = parseFloat(this.data.payForm.wechat_amount) || 0
      if (wallet < 0 || wechat < 0) {
        wx.showToast({ title: '金额不能为负', icon: 'none' })
        return
      }
      payload.wallet_amount = wallet
      payload.wechat_amount = wechat
      payload.coupon_id = this.data.payForm.coupon_id
      this.setData({ showPaymentModal: false })
    }

    api.post('/api/wallet/pay', payload).then(res => {
      if (method === 'wechat' && res && res.jsapi_params) {
        wx.requestPayment({
          ...res.jsapi_params,
          success: () => {
            wx.showToast({ title: '支付成功' })
            this.loadOrder(this.data.orderId)
          },
          fail: () => wx.showToast({ title: '支付取消', icon: 'none' })
        })
      } else {
        wx.showToast({ title: '支付成功' })
        this.loadOrder(this.data.orderId)
      }
    }).catch(() => wx.showToast({ title: '支付失败', icon: 'none' }))
  },

  confirmComplete() {
    wx.showModal({
      title: '确认完成',
      content: '确认该订单服务已全部完成吗？',
      success: res => {
        if (res.confirm) {
          api.put(`/api/orders/${this.data.orderId}/status`, { status: 'reviewed' })
            .then(() => {
              wx.showToast({ title: '已确认完成' })
              this.loadOrder(this.data.orderId)
            })
            .catch(() => wx.showToast({ title: '操作失败', icon: 'none' }))
        }
      }
    })
  },

  toggleReview() {
    this.setData({ showReview: !this.data.showReview })
  },

  setRating(e) {
    this.setData({ 'review.rating': e.currentTarget.dataset.rating })
  },

  toggleTag(e) {
    const tag = e.currentTarget.dataset.tag
    let tags = [...this.data.review.tags]
    const idx = tags.indexOf(tag)
    if (idx >= 0) tags.splice(idx, 1)
    else tags.push(tag)
    this.setData({ 'review.tags': tags })
  },

  onContentInput(e) {
    this.setData({ 'review.content': e.detail.value })
  },

  toggleAnonymous() {
    this.setData({ 'review.anonymous': !this.data.review.anonymous })
  },

  chooseImage() {
    const remaining = 5 - this.data.review.images.length
    if (remaining <= 0) { wx.showToast({ title: '最多5张图', icon: 'none' }); return }
    wx.chooseImage({
      count: remaining,
      success: res => {
        const images = [...this.data.review.images, ...res.tempFilePaths]
        this.setData({ 'review.images': images })
      }
    })
  },

  removeImage(e) {
    const idx = e.currentTarget.dataset.index
    const images = [...this.data.review.images]
    images.splice(idx, 1)
    this.setData({ 'review.images': images })
  },

  submitReview() {
    const { rating, tags, content, anonymous } = this.data.review
    if (!rating || rating < 1) { wx.showToast({ title: '请选择评分', icon: 'none' }); return }
    api.post(`/api/orders/${this.data.orderId}/review`, {
      rating, review_tags: tags, review_content: content, is_anonymous: anonymous
    }).then(() => {
      wx.showToast({ title: '评价成功' })
      this.setData({ showReview: false })
      this.loadOrder(this.data.orderId)
    }).catch(() => wx.showToast({ title: '提交失败', icon: 'none' }))
  },

  workerDetail() {
    wx.navigateTo({ url: `/pages/worker/detail/detail?worker_id=${this.data.order?.worker_id}` })
  },

  serviceDetail() {
    wx.navigateTo({ url: `/pages/service/detail/detail?key=${this.data.order?.service_type}` })
  },

  previewImage(e) {
    const url = e.currentTarget.dataset.url
    wx.previewImage({
      current: url,
      urls: this.data.order.images
    })
  }
})

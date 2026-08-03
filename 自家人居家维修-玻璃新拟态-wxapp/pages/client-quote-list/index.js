// pages/client-quote-list/index.js — 师傅报价列表 玻璃新拟态
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

// 排序选项
const SORT_OPTIONS = [
  { key: 'price_asc',  name: '价格从低到高' },
  { key: 'rating_desc', name: '评分从高到低' },
  { key: 'distance_asc', name: '距离最近' }
]

Page({
  data: {
    statusBarHeight: 20,
    orderId: '',
    orderNo: '',
    serviceName: '',
    sortOptions: SORT_OPTIONS,
    sortKey: 'price_asc',
    biddings: [],
    rawBiddings: [],
    icons: {}
  },

  onLoad(query) {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      orderId: query.orderId || query.id || '',
      orderNo: query.orderNo || query.no || '',
      serviceName: query.serviceName || query.service || '',
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        service: buildIcon('droplet', COLORS.brand),
        count: buildIcon('user', COLORS.brand),
        star: buildIcon('star', COLORS.accent),
        location: buildIcon('location', COLORS.text3),
        clock: buildIcon('clock', COLORS.text3),
        verify: buildIcon('shield', COLORS.brand),
        check: buildIcon('check', COLORS.white),
        safety: buildIcon('shield', COLORS.brand),
        empty: buildIcon('orders', COLORS.text3),
        user: buildIcon('user', COLORS.text3)
      }
    })
    this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    const orderId = this.data.orderId
    if (!orderId) {
      wx.showToast({ title: '缺少订单参数', icon: 'none' })
      return
    }
    wx.showLoading({ title: '加载报价', mask: true })
    try {
      const res = await api.orders.listBiddings(orderId)
      const list = (res && res.biddings) || res || []
      // 兜底：补全头像与字段；后端返回 worker_avatar/worker_rating/worker_name(snake) 需映射
      const raw = list.map(b => {
        const rating = b.rating != null ? b.rating : (b.worker_rating != null ? b.worker_rating : 5)
        return Object.assign({}, b, {
          workerName: b.worker_name != null ? b.worker_name : b.workerName,
          workerAvatar: b.worker_avatar != null ? b.worker_avatar : b.workerAvatar,
          rating: rating,
          avatarUrl: b.workerAvatar || b.worker_avatar || buildIcon('user', COLORS.brand),
          ratingText: rating.toFixed(1),
          distanceText: b.distance != null ? (b.distance + 'km') : '—',
          etaText: b.eta || '—',
          priceText: b.price != null ? b.price : '—'
        })
      })
      this.setData({ rawBiddings: raw })
      this.applySort()
      // 若后端在响应里附带订单号 / 服务名，回填
      if (res && res.orderNo && !this.data.orderNo) this.setData({ orderNo: res.orderNo })
      if (res && res.serviceName && !this.data.serviceName) this.setData({ serviceName: res.serviceName })
    } catch (e) {
      console.error('加载报价失败', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  // 本地排序
  applySort() {
    const raw = this.data.rawBiddings.slice()
    const key = this.data.sortKey
    let sorted = raw
    if (key === 'price_asc') {
      sorted = raw.sort((a, b) => (a.price || 0) - (b.price || 0))
    } else if (key === 'rating_desc') {
      sorted = raw.sort((a, b) => (b.rating || 0) - (a.rating || 0))
    } else if (key === 'distance_asc') {
      sorted = raw.sort((a, b) => (a.distance || 0) - (b.distance || 0))
    }
    this.setData({ biddings: sorted })
  },

  onSortTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.sortKey) return
    this.setData({ sortKey: key })
    this.applySort()
  },

  onSelectTap(e) {
    const biddingId = e.currentTarget.dataset.id
    const orderId = this.data.orderId
    if (!biddingId || !orderId) return
    wx.showModal({
      title: '确认选择',
      content: '确定选择该师傅的报价吗？选择后其他报价将失效。',
      confirmColor: '#0D9488',
      success: async (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '提交中', mask: true })
        try {
          const api = app.getApi()
          await api.orders.selectBidding(orderId, biddingId)
          wx.hideLoading()
          wx.showToast({ title: '已选择报价', icon: 'success' })
          setTimeout(() => wx.navigateBack({ delta: 1 }), 800)
        } catch (err) {
          wx.hideLoading()
          console.error('选择报价失败', err)
          wx.showToast({ title: '选择失败', icon: 'none' })
        }
      }
    })
  },

  onViewWorker(e) {
    const biddingId = e.currentTarget.dataset.id
    if (!biddingId) return
    wx.navigateTo({
      url: '/pages/client-favorite-workers/index?id=' + biddingId,
      fail: () => wx.showToast({ title: '暂未开放', icon: 'none' })
    })
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-orders/index' }) })
  }
})

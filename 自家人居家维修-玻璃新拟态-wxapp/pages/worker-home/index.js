// pages/worker-home/index.js — 师傅端接单大厅（主样式规范）
// 筛选4项：全部/附近/高价/急单，订单操作"立即报价"
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    filters: [
      { key: 'all',    name: '全部' },
      { key: 'nearby', name: '附近' },
      { key: 'high',   name: '高价' },
      { key: 'urgent', name: '急单' }
    ],
    activeFilter: 'all',
    orders: [],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        filter: buildIcon('filter', COLORS.text1),
        location: buildIcon('location', COLORS.text3),
        clock: buildIcon('clock', COLORS.text3),
        orders: buildIcon('orders', COLORS.text3),
        edit: buildIcon('edit', COLORS.brandWorker)
      }
    })
    this.loadOrders()
  },

  onShow() {
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
  },

  async loadOrders() {
    const api = app.getApi()
    try {
      // 接单大厅：取可抢订单（后端 /api/orders/available 返回 status=pending 且该师傅未竞价）
      const all = await api.orders.available({})
      // 规范化字段：后端 OrderResponse + available 端点附加 distance_meters/distance_text
      let list = (all || []).map(o => Object.assign({}, o, {
        // service_name → serviceName（页面与报价弹窗使用）
        serviceName: o.serviceName || o.service_name || '',
        // 价格区间：后端无 priceRange，由 budget 派生
        priceRange: o.priceRange || (o.budget ? ('¥' + o.budget) : ''),
        // 距离 km：后端 distance_meters(米) → 前端 distance(km)
        distance: o.distance != null ? o.distance : (o.distance_meters != null ? o.distance_meters / 1000 : null),
        distanceText: o.distanceText || o.distance_text || '',
        icon: o.icon || 'orders'
      }))
      const filter = this.data.activeFilter
      if (filter === 'nearby') list = list.filter(o => o.distance != null && o.distance <= 2)
      if (filter === 'high')   list = list.filter(o => {
        // 解析价格区间，筛选高价订单（起价 >= 150）
        const priceStr = o.priceRange || ''
        const match = priceStr.match(/(\d+)/)
        return match && parseInt(match[1]) >= 150
      })
      if (filter === 'urgent') list = list.filter(o => o.urgent)
      const withIcons = list.map(o => Object.assign({}, o, {
        iconUrl: buildIcon(o.icon, COLORS.brandWorker)
      }))
      this.setData({ orders: withIcons })
    } catch (e) {
      console.error('加载订单失败', e)
    }
  },

  onFilterTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeFilter) return
    this.setData({ activeFilter: key })
    this.loadOrders()
  },

  // 筛选设置按钮
  onFilterSettings() {
    wx.showToast({ title: '筛选设置', icon: 'none' })
  },

  // 查看全部
  onViewAll() {
    wx.navigateTo({ url: '/pages/worker-orders/index' })
  },

  onOrderTap(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/order-detail-worker/index?id=' + id })
  },

  // 立即报价
  onQuoteTap(e) {
    const id = e.currentTarget.dataset.id
    const order = this.data.orders.find(o => o.id === id)
    if (!order) return
    wx.showModal({
      title: '确认报价',
      content: `服务：${order.serviceName}\n价格区间：${order.priceRange}`,
      confirmText: '提交报价',
      confirmColor: '#2D6CDF',
      success: async (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '提交中...' })
        const api = app.getApi()
        try {
          // 解析报价金额：从 priceRange 取首个数字，降级到 budget；调用竞价端点
          const priceMatch = (order.priceRange || '').match(/(\d+(\.\d+)?)/)
          const price = priceMatch ? Number(priceMatch[1]) : (order.budget || 0)
          await api.orders.bidding(id, { price: price })
          wx.hideLoading()
          wx.showToast({ title: '报价成功', icon: 'success' })
          setTimeout(() => {
            wx.redirectTo({ url: '/pages/worker-orders/index' })
          }, 1200)
        } catch (e) {
          wx.hideLoading()
          wx.showToast({ title: '报价失败', icon: 'none' })
        }
      }
    })
  }
})

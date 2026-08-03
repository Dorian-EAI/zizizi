const api = require('../../../utils/request')

const WORKER_TABS = [
  { key: 'home', text: '首页', path: '/pages/worker/index/index' },
  { key: 'orders', text: '订单', path: '/pages/worker/orders/orders' },
  { key: 'review', text: '评价', path: '/pages/review/list/list' },
  { key: 'mine', text: '我的', path: '/pages/worker/profile/profile' }
]

const FILTER_OPTIONS = [
  { key: 'all', text: '全部' },
  { key: 'nearby', text: '附近' },
  { key: 'high_price', text: '高价' },
  { key: 'urgent', text: '紧急' }
]

Page({
  data: {
    stats: { today_income: 0, month_income: 0, pending_count: 0 },
    orders: [],
    filteredOrders: [],
    loading: true,
    currentTab: 'home',
    tabs: WORKER_TABS,
    worker_lat: null,
    worker_lng: null,
    hasDepartingOrder: false,
    filterOptions: FILTER_OPTIONS,
    activeFilter: 'all'
  },
  onLoad() {
    this.getWorkerLocation()
    this.loadData()
  },
  onShow() {
    this.loadData()
  },
  getWorkerLocation() {
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        this.setData({ worker_lat: res.latitude, worker_lng: res.longitude })
      },
      fail: () => {
        // 定位失败不打扰，仍可加载订单（无距离信息）
        this.setData({ worker_lat: null, worker_lng: null })
      }
    })
  },
  loadData() {
    this.loadStats()
    this.loadAvailableOrders()
  },
  loadStats() {
    api.get('/api/orders', { role: 'worker', page: 1, size: 100 }).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      const today = new Date()
      const todayStr = today.toISOString().slice(0, 10)
      const monthStr = today.toISOString().slice(0, 7)
      let todayIncome = 0, monthIncome = 0
      list.forEach(o => {
        const d = (o.completed_at || o.created_at || '').slice(0, 10)
        if (d === todayStr && (o.status === 'completed' || o.status === 'reviewed' || o.status === 'paid')) {
          todayIncome += parseFloat(o.final_price || o.total_amount || 0)
        }
        if (d.slice(0, 7) === monthStr && (o.status === 'completed' || o.status === 'reviewed' || o.status === 'paid')) {
          monthIncome += parseFloat(o.final_price || o.total_amount || 0)
        }
      })
      this.setData({
        stats: {
          today_income: todayIncome.toFixed(2),
          month_income: monthIncome.toFixed(2),
          pending_count: list.filter(o => o.status === 'accepted').length
        },
        hasDepartingOrder: list.some(o => o.status === 'departing')
      })
    }).catch(() => {})
  },
  loadAvailableOrders() {
    this.setData({ loading: true })
    const { worker_lat, worker_lng, activeFilter } = this.data
    const params = { status: 'pending', page: 1, size: 20 }
    const url = (worker_lat && worker_lng)
      ? '/api/orders/available'
      : '/api/orders'
    if (worker_lat && worker_lng) {
      params.lat = worker_lat
      params.lng = worker_lng
      params.sort_by = 'distance'
    }
    if (activeFilter === 'high_price') params.sort_by = 'price_desc'
    if (activeFilter === 'urgent') params.urgent = 1
    api.get(url, params).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      const orders = this.applyLocalFilters(list)
      this.setData({ orders: list, filteredOrders: orders, loading: false })
    }).catch(() => {
      const mockList = this.getMockOrders()
      this.setData({ orders: mockList, filteredOrders: this.applyLocalFilters(mockList), loading: false })
    })
  },
  applyLocalFilters(list) {
    const filter = this.data.activeFilter
    if (filter === 'all') return list
    if (filter === 'nearby') return list.filter(o => o.distance && parseFloat(o.distance) <= 5)
    if (filter === 'high_price') return list.filter(o => {
      const p = parseFloat(o.price_range || o.final_price || o.total_amount || 0)
      return p >= 200
    })
    if (filter === 'urgent') return list.filter(o => o.urgent || o.urgent_amount > 0)
    return list
  },
  getMockOrders() {
    return [
      { id: '1', service_name: '空调维修', service_type: '家电维修', distance: '2.3', publish_time: '10分钟前', price_range: '280', urgent: true, urgent_amount: 30, address: '北京市朝阳区望京SOHO' },
      { id: '2', service_name: '水管疏通', service_type: '水电维修', distance: '5.1', publish_time: '25分钟前', price_range: '168', urgent: false, urgent_amount: 0, address: '北京市海淀区中关村' },
      { id: '3', service_name: '电路检修', service_type: '水电维修', distance: '1.2', publish_time: '30分钟前', price_range: '350', urgent: true, urgent_amount: 50, address: '北京市西城区金融街' },
      { id: '4', service_name: '门窗维修', service_type: '综合维修', distance: '8.7', publish_time: '1小时前', price_range: '120', urgent: false, urgent_amount: 0, address: '北京市东城区东单' }
    ]
  },
  onFilterChange(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ activeFilter: key }, () => {
      const filtered = this.applyLocalFilters(this.data.orders)
      this.setData({ filteredOrders: filtered })
    })
  },
  onFilterTap() {
    wx.showToast({ title: '筛选功能开发中', icon: 'none' })
  },
  openNavigation(e) {
    const { latitude, longitude, name, address } = e.currentTarget.dataset
    if (!latitude || !longitude) {
      wx.showToast({ title: '该订单无位置信息', icon: 'none' })
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
  grabOrder(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '接单报价',
      editable: true,
      placeholderText: '请输入您的报价金额',
      success: res => {
        if (res.confirm) {
          const price = parseFloat(res.content)
          if (!price || price <= 0) {
            wx.showToast({ title: '请输入有效金额', icon: 'none' })
            return
          }
          api.post(`/api/orders/${id}/bidding`, { price }).then(() => {
            wx.showToast({ title: '报价成功' })
            this.loadAvailableOrders()
          }).catch(() => wx.showToast({ title: '报价失败', icon: 'none' }))
        }
      }
    })
  },
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/worker/detail/detail?order_id=${id}` })
  },
  onTabTap(e) {
    const path = e.currentTarget.dataset.path
    if (path === '/pages/review/list/list') {
      wx.navigateTo({ url: path })
      return
    }
    wx.redirectTo({ url: path })
  }
})

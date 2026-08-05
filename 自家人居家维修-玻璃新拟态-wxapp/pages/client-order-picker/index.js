const app = getApp()
const { STATUS_TEXT } = require('../../utils/order-status')

const ACTIVE_STATUSES = ['accepted', 'departing', 'arrived', 'serving', 'pending']
const AFTER_SALE_STATUSES = ['completed', 'paid', 'pending_review', 'reviewed']

const TABS = [
  { key: 'all', name: '全部' },
  { key: 'active', name: '进行中' },
  { key: 'aftersale', name: '售后' }
]

Page({
  data: {
    statusBarHeight: 20,
    tabs: TABS,
    activeTab: 'all',
    keyword: '',
    orders: [],
    filteredOrders: [],
    selectedOrderId: '',
    loading: false,
    loadError: false,
    empty: true,
    selectedCount: 0
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20
    })
    this.loadOrders()
  },

  onShow() {
    if (this.data.loadError || (!this.data.loading && this.data.orders.length === 0)) {
      this.loadOrders()
    }
  },

  async loadOrders() {
    const api = app.getApi()
    this.setData({ loading: true, loadError: false })
    try {
      const rawOrders = await api.orders.list()
      const orders = Array.isArray(rawOrders) ? rawOrders.map(o => this._normalizeOrder(o)) : []
      this.setData({ orders, loading: false })
      this._applyFilter()
    } catch (e) {
      console.error('加载订单失败', e)
      this.setData({ loading: false, loadError: true, orders: [], filteredOrders: [], empty: true })
    }
  },

  _normalizeOrder(o) {
    const status = o.status === 'cancelled' ? 'canceled' : o.status
    const statusText = o.statusText || STATUS_TEXT[status] || status
    const orderNo = o.order_no || o.orderNo || o.id || ''
    const serviceName = o.service_name || o.serviceName || o.title || '未知服务'
    const amount = o.amount || o.total_amount || o.price || 0
    return Object.assign({}, o, {
      status,
      statusText,
      orderNo: String(orderNo),
      serviceName: String(serviceName),
      amount: Number(amount)
    })
  },

  _applyFilter() {
    const { orders, activeTab, keyword, selectedOrderId } = this.data
    const kw = String(keyword || '').trim().toLowerCase()

    const tabFiltered = orders.filter(o => {
      if (activeTab === 'active') return ACTIVE_STATUSES.indexOf(o.status) >= 0
      if (activeTab === 'aftersale') return AFTER_SALE_STATUSES.indexOf(o.status) >= 0
      return true
    })

    const searchFiltered = kw
      ? tabFiltered.filter(o =>
          (o.orderNo && o.orderNo.toLowerCase().indexOf(kw) >= 0) ||
          (o.serviceName && o.serviceName.toLowerCase().indexOf(kw) >= 0)
        )
      : tabFiltered

    const selectedCount = searchFiltered.filter(o => String(o.id) === String(selectedOrderId)).length

    this.setData({
      filteredOrders: searchFiltered,
      empty: searchFiltered.length === 0,
      selectedCount
    })
  },

  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (!key || key === this.data.activeTab) return
    this.setData({ activeTab: key })
    this._applyFilter()
  },

  onSearchInput(e) {
    const keyword = e.detail.value || ''
    this.setData({ keyword })
    this._applyFilter()
  },

  onClearSearch() {
    this.setData({ keyword: '' })
    this._applyFilter()
  },

  onSelectOrder(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    this.setData({ selectedOrderId: String(id) })
    this._applyFilter()
  },

  onConfirm() {
    const { selectedOrderId, orders } = this.data
    if (!selectedOrderId) {
      wx.showToast({ title: '请先选择一个订单', icon: 'none' })
      return
    }
    const order = orders.find(o => String(o.id) === String(selectedOrderId))
    if (!order) {
      wx.showToast({ title: '订单不存在', icon: 'none' })
      return
    }

    const payload = {
      id: order.id,
      order_no: order.orderNo,
      service_name: order.serviceName,
      status: order.status,
      statusText: order.statusText,
      amount: order.amount
    }

    const eventChannel = this.getOpenerEventChannel && this.getOpenerEventChannel()
    if (eventChannel && eventChannel.emit) {
      eventChannel.emit('orderSelected', payload)
    }

    wx.navigateBack({
      delta: 1,
      fail: () => {
        wx.showToast({ title: '返回上一页失败', icon: 'none' })
      }
    })
  },

  onBack() {
    wx.navigateBack({
      delta: 1,
      fail: () => {
        wx.showToast({ title: '已返回', icon: 'none' })
      }
    })
  },

  onRetry() {
    this.loadOrders()
  }
})

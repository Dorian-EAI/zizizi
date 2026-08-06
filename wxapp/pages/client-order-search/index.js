// pages/client-order-search/index.js — 客户端订单搜索（玻璃新拟态）
const app = getApp()
const { STATUS_TEXT } = require('../../utils/order-status')

const HISTORY_KEY = '__CLIENT_ORDER_SEARCH_HISTORY__'

function normalizeArray(value) {
  return Array.isArray(value) ? value : []
}

function pad(num) {
  num = Number(num) || 0
  return num < 10 ? '0' + num : '' + num
}

function formatTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (isNaN(d.getTime())) return ''
  const today = new Date()
  const sameDay = d.getFullYear() === today.getFullYear() &&
                  d.getMonth() === today.getMonth() &&
                  d.getDate() === today.getDate()
  const time = pad(d.getHours()) + ':' + pad(d.getMinutes())
  if (sameDay) return '今日 ' + time
  return (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + time
}

function matchOrder(order, keyword) {
  if (!order || !keyword) return false
  const kw = String(keyword).trim().toLowerCase()
  if (!kw) return false
  const haystack = [
    order.order_no,
    order.orderNo,
    order.service_name,
    order.serviceName,
    order.service_key,
    order.worker_name,
    order.workerName,
    order.worker_nickname,
    order.address,
    order.remark
  ].filter(Boolean).join(' ').toLowerCase()
  return haystack.indexOf(kw) !== -1
}

function buildOrderRow(order) {
  const status = order.status === 'cancelled' ? 'canceled' : order.status
  const statusText = order.statusText || STATUS_TEXT[status] || '处理中'
  const amount = order.final_amount != null
    ? order.final_amount
    : (order.amount != null ? order.amount : order.total_amount)
  const amountText = amount != null ? '¥' + Number(amount).toFixed(0) : '价格待定'
  const orderNo = order.order_no || order.orderNo || order.id || ''
  const orderNoShort = orderNo.length > 8 ? '#' + orderNo.slice(-6) : '#' + orderNo
  const workerName = order.worker_name || order.workerName || order.worker_nickname || '待分配师傅'
  const serviceName = order.service_name || order.serviceName || '服务订单'
  const timeText = formatTime(order.appointment_time || order.created_at || order.createdAt)
  const statusClass = 'badge info'
  return Object.assign({}, order, {
    _statusText: statusText,
    _statusClass: statusClass,
    _amountText: amountText,
    _orderNoShort: orderNoShort,
    _workerName: workerName,
    _serviceName: serviceName,
    _timeText: timeText,
    _displaySub: orderNoShort + ' · ' + workerName + (timeText ? ' · ' + timeText : '')
  })
}

Page({
  data: {
    keyword: '',
    history: [],
    hotTags: [],
    hotServices: [],
    orders: [],
    searched: false,
    loading: false,
    loadError: '',
    orderCount: 0
  },

  onLoad(query) {
    this.loadHistory()
    this.loadHotTags()
    const keyword = String(query && query.keyword || '').trim().slice(0, 40)
    if (keyword) {
      this.setData({ keyword })
      this.search()
    }
  },

  loadHistory() {
    try {
      const value = wx.getStorageSync(HISTORY_KEY)
      this.setData({ history: Array.isArray(value) ? value.filter(Boolean).slice(0, 10) : [] })
    } catch (error) {
      this.setData({ history: [] })
    }
  },

  async loadHotTags() {
    try {
      const tags = await app.getApi().services.hotTags()
      const list = normalizeArray(tags).map(String).filter(Boolean).slice(0, 6)
      this.setData({ hotTags: list })
      this.setData({ hotServices: list.map((name, i) => ({
        rank: pad(i + 1),
        name,
        desc: ['热门', '推荐', '好评'][i] || '居家维修服务'
      })) })
    } catch (error) {
      console.warn('加载热门搜索失败', error)
    }
  },

  onInput(e) {
    this.setData({ keyword: String(e.detail.value || '').slice(0, 40) })
  },

  onUseKeyword(e) {
    const keyword = String(e.currentTarget.dataset.keyword || '').trim()
    if (!keyword) return
    this.setData({ keyword })
    this.search()
  },

  onClearHistoryTap() {
    wx.showModal({
      title: '确认清空',
      content: '确定要清空所有搜索历史吗？',
      success: (res) => {
        if (res.confirm) {
          try { wx.removeStorageSync(HISTORY_KEY) } catch (error) {}
          this.setData({ history: [] })
        }
      }
    })
  },

  async search() {
    const keyword = String(this.data.keyword || '').trim()
    if (!keyword) {
      wx.showToast({ title: '请输入搜索内容', icon: 'none' })
      return
    }
    if (this.data.loading) return
    this.setData({ loading: true, searched: true, loadError: '', orders: [], orderCount: 0 })

    try {
      const api = app.getApi()
      const [ordersResult, servicesResult] = await Promise.allSettled([
        api.orders && api.orders.list ? api.orders.list() : Promise.resolve([]),
        api.services.search(keyword)
      ])

      let allOrders = []
      if (ordersResult.status === 'fulfilled') {
        allOrders = normalizeArray(ordersResult.value)
      } else {
        console.warn('加载订单列表失败', ordersResult.reason)
      }

      let matchedOrders = allOrders.filter(o => matchOrder(o, keyword))

      if (matchedOrders.length === 0 && servicesResult.status === 'fulfilled') {
        const services = normalizeArray(servicesResult.value && servicesResult.value.services)
        if (services.length > 0) {
          const serviceNames = services.map(s => s.name).filter(Boolean)
          if (serviceNames.length > 0) {
            matchedOrders = allOrders.filter(o => {
              const name = String(o.service_name || o.serviceName || '').toLowerCase()
              return serviceNames.some(s => name.indexOf(String(s).toLowerCase()) !== -1)
            })
          }
        }
      }

      if (matchedOrders.length === 0 && keyword) {
        const kw = keyword.toLowerCase()
        matchedOrders = allOrders.filter(o => {
          const list = [o.service_name, o.serviceName, o.worker_name, o.workerName, o.order_no, o.orderNo]
            .filter(Boolean).join(' ').toLowerCase()
          return list.indexOf(kw) !== -1
        })
      }

      const orders = matchedOrders.map(buildOrderRow)

      try {
        const history = [keyword]
          .concat(this.data.history.filter(item => item !== keyword))
          .slice(0, 10)
        wx.setStorageSync(HISTORY_KEY, history)
        this.setData({ history })
      } catch (error) {
        console.warn('保存搜索历史失败', error)
      }

      this.setData({ orders, orderCount: orders.length, loading: false })
    } catch (error) {
      console.error('搜索失败', error)
      this.setData({
        orders: [],
        orderCount: 0,
        loading: false,
        loadError: (error && error.message) || '搜索失败，请稍后重试'
      })
    }
  },

  onClearInput() {
    this.setData({ keyword: '', searched: false, orders: [], orderCount: 0, loadError: '' })
  },

  onRetry() {
    this.search()
  },

  onBack() {
    if (this.data.searched && this.data.keyword) {
      this.setData({ keyword: '', searched: false, orders: [], orderCount: 0, loadError: '' })
      return
    }
    wx.navigateBack({ delta: 1 })
  },

  onCancel() {
    wx.navigateBack({ delta: 1 })
  },

  onOrderTap(e) {
    const id = e.currentTarget.dataset.id
    if (id) {
      wx.navigateTo({ url: '/pages/order-detail-client/index?id=' + encodeURIComponent(id) })
    }
  }
})

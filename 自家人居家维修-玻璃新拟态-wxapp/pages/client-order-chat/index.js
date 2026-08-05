// pages/client-order-chat/index.js — 订单沟通页（真实 API 接入）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { STATUS_TEXT } = require('../../utils/order-status')

const STATUS_TITLE = {
  pending: '等待师傅接单',
  bidding: '师傅正在报价',
  accepted: '师傅已接单',
  departing: '师傅出发中',
  arrived: '师傅已到达',
  serving: '师傅服务中',
  completed: '服务已完成',
  paid: '待评价',
  pending_review: '待评价',
  reviewed: '订单已完成',
  canceled: '订单已取消',
  cancelled: '订单已取消',
  closed: '订单已关闭'
}

const QUICK_ACTIONS = [
  { key: 'location', text: '我在家，请直接上门' },
  { key: 'call',     text: '到门口请电话联系' },
  { key: 'ready',    text: '已准备好，随时可以进门' },
  { key: 'poweroff', text: '已关闭漏水位置附近电源' }
]

Page({
  data: {
    statusBarHeight: 20,
    orderId: '',
    order: {},
    worker: {},
    workerName: '',
    workerAvatarText: '',
    workerAvatarUrl: '',
    workerOnline: false,
    orderServiceName: '',
    orderNo: '',
    orderStatusText: '',
    orderStatusBadge: '进行中',
    orderStatusTone: 'warning',
    messages: [],
    emptyText: '本订单暂无聊天消息',
    loading: false,
    loadError: false,
    inputValue: '',
    quickActions: QUICK_ACTIONS,
    icons: {}
  },

  onLoad(query) {
    const orderId = (query && (query.id || query.orderId)) || ''
    this.setData({
      orderId,
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        phone: buildIcon('phone', COLORS.brand),
        user: buildIcon('user', '#FFFFFF')
      }
    })
    if (!orderId) {
      this.setData({
        loadError: true,
        emptyText: '订单参数缺失，无法加载沟通信息'
      })
      return
    }
    this.loadOrder(orderId)
  },

  async loadOrder(id) {
    this.setData({ loading: true, loadError: false })
    const api = app.getApi()
    try {
      const order = await api.orders.detail(id)
      const worker = this.extractWorker(order)
      const workerName = worker.name || worker.worker_name || worker.nickname || '师傅'
      const serviceName = order.service_name || order.serviceName || order.service_type || '维修服务'
      const orderNo = order.order_no || order.orderNo || ''
      const status = order.status || ''
      const statusText = STATUS_TITLE[status] || STATUS_TEXT[status] || '进行中'
      const badgeTone = this.badgeTone(status)

      this.setData({
        loading: false,
        loadError: false,
        order,
        worker,
        workerName,
        workerAvatarText: (workerName || '师').slice(-1),
        workerAvatarUrl: worker.avatar || worker.avatar_url || '',
        workerOnline: Boolean(worker.online || worker.is_online || status === 'departing' || status === 'serving' || status === 'arrived'),
        orderServiceName: serviceName,
        orderNo,
        orderStatusText: statusText,
        orderStatusBadge: statusText,
        orderStatusTone: badgeTone,
        messages: [],
        emptyText: '本订单暂无聊天消息'
      })

      wx.setNavigationBarTitle({ title: workerName })
    } catch (e) {
      console.error('加载订单沟通信息失败', e)
      this.setData({
        loading: false,
        loadError: true,
        emptyText: '加载失败，请点击重试'
      })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  extractWorker(order) {
    if (!order) return {}
    return order.worker || order.worker_info || order.workerInfo || {}
  },

  badgeTone(status) {
    if (status === 'completed' || status === 'paid' || status === 'reviewed' || status === 'pending_review') {
      return 'success'
    }
    if (status === 'canceled' || status === 'cancelled' || status === 'closed') {
      return 'muted'
    }
    return 'warning'
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onCallWorker() {
    const phone = String(this.data.worker.phone || this.data.worker.phone_number || '').trim()
    if (!phone) {
      wx.showToast({ title: '暂无师傅联系方式', icon: 'none' })
      return
    }
    wx.makePhoneCall({ phoneNumber: phone })
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value })
  },

  onSend() {
    const text = (this.data.inputValue || '').trim()
    if (!text) {
      wx.showToast({ title: '请输入消息内容', icon: 'none' })
      return
    }
    this.appendLocalMessage(text)
    this.setData({ inputValue: '' })
  },

  onQuickTap(e) {
    const text = e.currentTarget.dataset.text
    if (!text) return
    this.appendLocalMessage(text)
  },

  appendLocalMessage(text) {
    const time = this.fmtTime(Date.now())
    const msg = {
      id: 'local_' + Date.now(),
      isSelf: true,
      content: text,
      time: time,
      status: 'sent'
    }
    const messages = (this.data.messages || []).concat([msg])
    this.setData({ messages })
    wx.showToast({ title: '已发送', icon: 'none', duration: 800 })
  },

  fmtTime(ts) {
    const d = new Date(ts)
    const pad = (n) => (n < 10 ? '0' + n : '' + n)
    return pad(d.getHours()) + ':' + pad(d.getMinutes())
  },

  onRetry() {
    if (this.data.orderId) {
      this.loadOrder(this.data.orderId)
    }
  },

  onGoOrderDetail() {
    if (this.data.orderId) {
      wx.navigateTo({ url: '/pages/order-detail-client/index?id=' + this.data.orderId })
    } else {
      wx.navigateBack({ delta: 1 })
    }
  },

  onOpenImagePicker() {
    wx.showToast({ title: '图片功能暂未开放', icon: 'none' })
  }
})

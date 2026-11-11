const app = getApp()

const REASON_OPTIONS = [
  { key: 'plan_changed', label: '计划有变' },
  { key: 'late', label: '师傅迟到' },
  { key: 'price', label: '价格问题' },
  { key: 'service', label: '服务不满意' },
  { key: 'other', label: '其他原因' }
]

function formatAmount(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '0.00'
  return num.toFixed(2)
}

function pickServiceName(order) {
  if (!order) return ''
  return order.service_name
    || (order.service && (order.service.name || order.service.title))
    || order.title
    || ''
}

function pickOrderNo(order) {
  if (!order) return ''
  return order.order_no || order.orderNo || order.id || ''
}

function pickAmount(order) {
  if (!order) return 0
  const candidates = [
    order.final_amount,
    order.pay_amount,
    order.payable_amount,
    order.total_amount,
    order.amount,
    order.price
  ]
  for (let i = 0; i < candidates.length; i++) {
    const v = Number(candidates[i])
    if (Number.isFinite(v)) return v
  }
  return 0
}

function pickStatusText(order) {
  if (!order) return ''
  const map = {
    pending: '待上门',
    pending_confirm: '待确认',
    waiting: '待上门',
    assigned: '待上门',
    in_service: '服务中',
    servicing: '服务中',
    completed: '已完成',
    cancelled: '已取消'
  }
  const status = order.status || order.state || ''
  if (map[status]) return map[status]
  return order.status_text || order.state_text || ''
}

Page({
  data: {
    orderId: '',
    order: null,
    loading: true,
    loadError: false,
    errorMessage: '',
    empty: false,

    serviceName: '',
    orderNo: '',
    orderStatusText: '',
    amountText: '0.00',
    icon: '🔧',

    reasonOptions: REASON_OPTIONS,
    selectedReason: '',
    selectedReasonIndex: -1,
    note: '',

    cancelling: false,
    cancelled: false
  },

  onLoad(query) {
    const orderId = query && (query.orderId || query.id) ? String(query.orderId || query.id) : ''
    this.setData({ orderId })
    if (!orderId) {
      this.setData({
        loading: false,
        empty: true,
        errorMessage: '缺少订单标识'
      })
      wx.showToast({ title: '订单参数缺失', icon: 'none' })
      return
    }
    this.loadOrder()
  },

  async loadOrder() {
    if (!this.data.orderId) return
    this.setData({ loading: true, loadError: false, empty: false, errorMessage: '' })
    try {
      const api = app.getApi()
      const order = await api.orders.detail(this.data.orderId)
      if (!order) {
        this.setData({
          loading: false,
          empty: true,
          order: null,
          serviceName: '',
          orderNo: '',
          orderStatusText: '',
          amountText: '0.00'
        })
        return
      }
      this.setData({
        loading: false,
        order,
        serviceName: pickServiceName(order),
        orderNo: pickOrderNo(order),
        orderStatusText: pickStatusText(order),
        amountText: formatAmount(pickAmount(order))
      })
    } catch (error) {
      console.error('加载订单详情失败', error)
      this.setData({
        loading: false,
        loadError: true,
        errorMessage: (error && error.message) || '订单加载失败，请重试'
      })
      wx.showToast({ title: (error && error.message) || '加载失败', icon: 'none' })
    }
  },

  onSelectReason(e) {
    const index = Number(e.currentTarget.dataset.index)
    const option = this.data.reasonOptions[index]
    if (!option) return
    this.setData({
      selectedReason: option.key,
      selectedReasonIndex: index
    })
  },

  onNoteInput(e) {
    this.setData({ note: e.detail.value || '' })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onKeepOrder() {
    wx.navigateBack({ delta: 1 })
  },

  onRetryLoad() {
    this.loadOrder()
  },

  async onConfirmCancel() {
    if (this.data.cancelling) return
    if (!this.data.orderId) {
      wx.showToast({ title: '订单参数缺失', icon: 'none' })
      return
    }
    if (!this.data.selectedReason) {
      wx.showToast({ title: '请选择取消原因', icon: 'none' })
      return
    }

    const reasonLabel = (REASON_OPTIONS.find(item => item.key === this.data.selectedReason) || {}).label || ''
    const extraNote = this.data.note ? `｜补充：${this.data.note}` : ''
    const cancelReason = `${reasonLabel}${extraNote}`

    wx.showModal({
      title: '确认取消订单？',
      content: '取消后订单将不再继续服务，退款将按原路返回。',
      confirmText: '确认取消',
      confirmColor: '#d9534f',
      success: async (res) => {
        if (!res.confirm) return
        this.setData({ cancelling: true })
        wx.showLoading({ title: '提交中', mask: true })
        try {
          const api = app.getApi()
          await api.orders.cancel(this.data.orderId, cancelReason)
          wx.hideLoading()
          this.setData({ cancelling: false, cancelled: true })
          wx.showToast({ title: '订单已取消', icon: 'success' })
          setTimeout(() => {
            this.goOrdersList()
          }, 800)
        } catch (error) {
          wx.hideLoading()
          this.setData({ cancelling: false })
          console.error('取消订单失败', error)
          wx.showToast({ title: (error && error.message) || '取消失败，请重试', icon: 'none' })
        }
      }
    })
  },

  goOrdersList() {
    const url = '/pages/client-orders/index'
    const pages = getCurrentPages()
    if (pages.length >= 2) {
      wx.navigateBack({ delta: pages.length - 1 })
      return
    }
    wx.reLaunch({ url })
  }
})

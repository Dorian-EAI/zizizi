const { createBusinessPage } = require('../../utils/design-business-page')
const { money, safePositiveId } = require('../../utils/client-finance')

function couponView(item) {
  const template = item && item.template || {}
  return Object.assign({}, item, {
    idText: String(item && item.id || ''),
    nameText: template.name || item.name || '优惠券',
    discountText: money(item.discount_amount),
    minSpendText: money(template.min_spend),
    expireText: item.expire_at || template.valid_end || '长期有效',
    serviceText: template.service_type ? ('限 ' + template.service_type + ' 服务') : '平台适用服务'
  })
}

Page(createBusinessPage(Object.freeze({
  pageId: 'page-client-coupon-select', route: 'pages/client-coupon-select/index',
  source: 'pages/client-coupon-select.html', sourceHash: 'fnv1a-a388a7d2', title: '选择优惠券'
}), {
  data: {
    orderId: 0, amount: 0, amountText: '—', serviceType: '', selectedId: '',
    selectedCoupon: null, coupons: [], loading: true, loadError: ''
  },

  onLoad(options) {
    this.setData({
      orderId: safePositiveId(options && options.orderId),
      amount: Number(options && options.amount) || 0,
      serviceType: String(options && options.serviceType || ''),
      selectedId: String(options && options.selectedId || '')
    })
    this.loadCoupons()
  },

  async loadCoupons() {
    this.setData({ loading: true, loadError: '' })
    try {
      let amount = this.data.amount
      let serviceType = this.data.serviceType
      if (this.data.orderId) {
        const api = getApp().getApi()
        const [quote, order] = await Promise.all([
          api.orders.paymentQuote(this.data.orderId),
          api.orders.detail(this.data.orderId)
        ])
        amount = Number(quote && quote.original_amount)
        serviceType = String(order && order.service_type || '')
      }
      if (!Number.isFinite(amount) || amount < 0) throw new Error('缺少有效订单金额')
      const raw = await getApp().getApi().coupon.available({ amount, service_type: serviceType || undefined })
      const coupons = (Array.isArray(raw) ? raw : []).map(couponView)
      const selectedCoupon = coupons.find(item => String(item.id) === this.data.selectedId) || null
      this.setData({
        loading: false, amount, amountText: money(amount), serviceType, coupons,
        selectedCoupon, selectedId: selectedCoupon ? String(selectedCoupon.id) : ''
      })
    } catch (error) {
      this.setData({ loading: false, coupons: [], selectedCoupon: null, selectedId: '', loadError: error.message || '可用优惠券加载失败' })
    }
  },

  onSelect(event) {
    const id = String(event.currentTarget.dataset.id || '')
    const selectedCoupon = this.data.coupons.find(item => String(item.id) === id) || null
    this.setData({ selectedId: selectedCoupon ? id : '', selectedCoupon })
  },

  onClear() {
    this.setData({ selectedId: '', selectedCoupon: null })
  },

  onDetail(event) {
    const id = event.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/package-client/pages/client-coupon-detail/index?couponId=' + encodeURIComponent(String(id)) })
  },

  onConfirm() {
    let channel = null
    try { channel = this.getOpenerEventChannel() } catch (error) {}
    if (channel && typeof channel.emit === 'function') {
      channel.emit('couponSelected', { coupon: this.data.selectedCoupon })
    }
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-orders/index' }) })
  }
}))

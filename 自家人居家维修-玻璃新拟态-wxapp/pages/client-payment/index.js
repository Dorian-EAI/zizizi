const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { requestPayment, isPaymentCancelled } = require('../../utils/wx-payment')
const idempotency = require('../../utils/idempotency')

const METHOD_META = {
  wechat: { name: '微信支付', desc: '微信支付 API v3', iconClass: 'wechat' },
  wallet: { name: '余额支付', desc: '使用可用用户余额', iconClass: 'balance' },
  combined: { name: '组合支付', desc: '余额与微信组合', iconClass: 'combo' },
  offline: { name: '线下支付', desc: '仅运营明确开启时可用', iconClass: 'offline' }
}
const FINAL_FAILURES = ['failed', 'closed', 'cancelled']
const POLL_DELAYS = [1000, 1500, 2500, 4000, 6000, 8000, 10000, 12000]
const PENDING_STORAGE_PREFIX = '__CLIENT_PAYMENT_PENDING__:'

Page({
  data: {
    orderId: '',
    order: null,
    quote: null,
    loading: true,
    loadError: false,
    paying: false,
    amount: 0,
    amountText: '0.00',
    payAmount: 0,
    payAmountText: '0.00',
    discountAmountText: '0.00',
    paymentMethods: [],
    selectedMethod: '',
    allowedActions: [],
    canPay: false,
    unavailableReason: '',
    coupons: [],
    selectedCoupon: null,
    pendingPaymentNo: '',
    resultChecking: false,
    icons: {}
  },

  onLoad(query) {
    this.setData({
      orderId: query && (query.orderId || query.id) ? String(query.orderId || query.id) : '',
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        help: buildIcon('info', COLORS.text1),
        wechat: buildIcon('wechat', COLORS.white),
        wallet: buildIcon('wallet', COLORS.white),
        combined: buildIcon('creditCard', COLORS.white),
        offline: buildIcon('yuan', COLORS.white),
        coupon: buildIcon('coupon', COLORS.white),
        arrow: buildIcon('chevronRight', COLORS.text3),
        shield: buildIcon('shield', COLORS.green)
      }
    })
    this.loadOrder()
  },

  onShow() {
    if (this.data.pendingPaymentNo) this.checkPaymentResult({ schedule: true })
  },

  onUnload() {
    this.clearPollTimer()
  },

  pendingStorageKey() {
    return PENDING_STORAGE_PREFIX + this.data.orderId
  },

  rememberPendingPayment(paymentNo) {
    const value = String(paymentNo || '')
    if (!value) return
    try { wx.setStorageSync(this.pendingStorageKey(), value) } catch (error) { console.warn('保存待查支付单失败', error) }
  },

  readPendingPayment() {
    try { return String(wx.getStorageSync(this.pendingStorageKey()) || '') } catch (error) { return '' }
  },

  clearPendingPayment() {
    try { wx.removeStorageSync(this.pendingStorageKey()) } catch (error) { console.warn('清理待查支付单失败', error) }
  },

  paymentAttemptSlot() {
    const quote = this.data.quote || {}
    const couponId = quote.coupon_id || 'none'
    return ['client-pay', this.data.orderId, this.data.selectedMethod || 'none', couponId, quote.order_version].join(':')
  },

  getPaymentAttemptKey() {
    const slot = this.paymentAttemptSlot()
    if (!this._paymentAttemptKey || this._paymentAttemptSlot !== slot) {
      this._paymentAttemptSlot = slot
      this._paymentAttemptKey = idempotency.getOrCreate(slot)
    }
    return this._paymentAttemptKey
  },

  clearPaymentAttempt() {
    if (this._paymentAttemptSlot) idempotency.clear(this._paymentAttemptSlot, this._paymentAttemptKey)
    this._paymentAttemptSlot = ''
    this._paymentAttemptKey = ''
  },

  normalizeMethods(quote) {
    const items = Array.isArray(quote && quote.payment_methods) ? quote.payment_methods : []
    return items.map(item => {
      const key = typeof item === 'string' ? item : (item.key || item.method || item.code)
      const meta = METHOD_META[key]
      if (!meta) return null
      const enabled = typeof item === 'string' ? true : item.enabled === true
      return Object.assign({}, meta, typeof item === 'object' ? item : {}, {
        key,
        enabled: enabled && key !== 'combined',
        disabledReason: key === 'combined'
          ? '服务端尚未返回可验证的拆分金额'
          : ((item && item.disabled_reason) || '')
      })
    }).filter(Boolean)
  },

  orderPermission(order) {
    const actions = Array.isArray(order && order.allowed_actions) ? order.allowed_actions : []
    return {
      actions,
      reason: actions.indexOf('confirm_and_pay') < 0 ? '服务端未授权当前订单支付' : ''
    }
  },

  applyQuote(order, quote, selectedCoupon) {
    const permission = this.orderPermission(order)
    const original = Number(quote && quote.original_amount)
    const payable = Number(quote && quote.payable_amount)
    const discount = Number(quote && quote.discount_amount)
    const methods = this.normalizeMethods(quote)
    const enabled = methods.filter(item => item.enabled)
    const active = quote && quote.active_payment
    let reason = permission.reason
    if (!quote || !Number.isInteger(Number(quote.order_version))) reason = reason || '服务端未返回有效支付报价版本'
    else if (!Number.isFinite(original) || original < 0 || !Number.isFinite(payable) || payable < 0) reason = reason || '服务端未返回有效支付金额'
    else if (!enabled.length && !active) reason = reason || '服务端未返回可用支付渠道'

    const selectedMethod = methods.some(item => item.key === this.data.selectedMethod && item.enabled)
      ? this.data.selectedMethod
      : ((enabled[0] || {}).key || '')
    const couponId = quote && quote.coupon_id
    const authoritativeCoupon = couponId
      ? Object.assign({}, selectedCoupon || {}, {
          id: couponId,
          name: (selectedCoupon && (selectedCoupon.name || selectedCoupon.template_name)) || '已选优惠券',
          discount_amount: Number.isFinite(discount) ? discount.toFixed(2) : '0.00'
        })
      : null
    const pendingPaymentNo = active && active.payment_no
      ? String(active.payment_no)
      : this.readPendingPayment()

    this.setData({
      order,
      quote,
      amount: Number.isFinite(original) ? original : 0,
      amountText: Number.isFinite(original) ? original.toFixed(2) : '0.00',
      payAmount: Number.isFinite(payable) ? payable : 0,
      payAmountText: Number.isFinite(payable) ? payable.toFixed(2) : '0.00',
      discountAmountText: Number.isFinite(discount) ? discount.toFixed(2) : '0.00',
      allowedActions: permission.actions,
      paymentMethods: methods,
      selectedMethod,
      selectedCoupon: authoritativeCoupon,
      pendingPaymentNo,
      resultChecking: !!pendingPaymentNo,
      canPay: !reason && !pendingPaymentNo,
      unavailableReason: reason
    })
    if (pendingPaymentNo) {
      this.rememberPendingPayment(pendingPaymentNo)
      this.schedulePaymentPoll(0)
    }
  },

  async fetchQuote(couponId) {
    return app.getApi().orders.paymentQuote(this.data.orderId, couponId || undefined)
  },

  async loadOrder() {
    if (!this.data.orderId) {
      this.setData({ loading: false, loadError: true, unavailableReason: '缺少订单标识' })
      return
    }
    this.setData({ loading: true, loadError: false })
    try {
      const api = app.getApi()
      const order = await api.orders.detail(this.data.orderId)
      const permission = this.orderPermission(order)
      if (permission.reason) {
        this.setData({
          order,
          quote: null,
          allowedActions: permission.actions,
          paymentMethods: [],
          selectedMethod: '',
          selectedCoupon: null,
          coupons: [],
          pendingPaymentNo: '',
          resultChecking: false,
          canPay: false,
          unavailableReason: permission.reason,
          loading: false
        })
        return
      }
      const quote = await api.orders.paymentQuote(this.data.orderId)
      this.applyQuote(order, quote, null)
      await this.loadCoupons()
      this.setData({ loading: false })
    } catch (error) {
      console.error('加载支付订单失败', error)
      this.setData({ loading: false, loadError: true, canPay: false, unavailableReason: (error && error.message) || '订单加载失败' })
    }
  },

  async loadCoupons() {
    if (!this.data.order || this.data.amount < 0) return
    try {
      const coupons = await app.getApi().coupon.available({
        amount: this.data.amount,
        service_type: this.data.order.service_type
      })
      const list = Array.isArray(coupons) ? coupons : []
      const selectedId = this.data.quote && this.data.quote.coupon_id
      const selected = selectedId ? list.find(item => String(item.id) === String(selectedId)) : null
      this.setData({ coupons: list })
      if (selectedId) this.applyQuote(this.data.order, this.data.quote, selected || this.data.selectedCoupon)
    } catch (error) {
      console.warn('可用优惠券加载失败', error)
      this.setData({ coupons: [] })
    }
  },

  onSelectMethod(e) {
    if (this.data.resultChecking) return
    const key = e.currentTarget.dataset.key
    const method = this.data.paymentMethods.find(item => item.key === key)
    if (!method || !method.enabled) {
      wx.showToast({ title: (method && method.disabledReason) || '该支付方式不可用', icon: 'none' })
      return
    }
    this.setData({ selectedMethod: key })
  },

  onCoupon() {
    if (this.data.resultChecking) {
      wx.showToast({ title: '待支付单处理中，不能更换优惠券', icon: 'none' })
      return
    }
    if (!this.data.coupons.length && !this.data.selectedCoupon) {
      wx.showToast({ title: '当前订单没有可用优惠券', icon: 'none' })
      return
    }
    const query = [
      'orderId=' + encodeURIComponent(this.data.orderId),
      'amount=' + encodeURIComponent(String(this.data.amount)),
      'serviceType=' + encodeURIComponent(String(this.data.order && this.data.order.service_type || '')),
      'selectedId=' + encodeURIComponent(String(this.data.selectedCoupon && this.data.selectedCoupon.id || ''))
    ].join('&')
    wx.navigateTo({
      url: '/pages/client-coupon-select/index?' + query,
      events: {
        couponSelected: payload => {
          const selected = payload && payload.coupon || null
          // 服务端 payment-quote 会重新校验券、订单金额与 order_version；
          // 回传的页面数据本身从不直接改变应付金额。
          this.refreshQuoteForCoupon(selected)
        }
      }
    })
  },

  async refreshQuoteForCoupon(selected) {
    wx.showLoading({ title: '正在重新计价', mask: true })
    try {
      const quote = await this.fetchQuote(selected && selected.id)
      this.clearPaymentAttempt()
      this.applyQuote(this.data.order, quote, selected)
    } catch (error) {
      console.error('优惠券重新计价失败', error)
      wx.showToast({ title: (error && error.message) || '优惠券不可用', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  async onPay() {
    if (!this.data.canPay || this.data.paying || this.data.resultChecking) {
      if (this.data.unavailableReason) wx.showToast({ title: this.data.unavailableReason, icon: 'none' })
      return
    }
    const intendedMethod = this.data.selectedMethod
    const couponId = this.data.quote && this.data.quote.coupon_id
    this.setData({ paying: true })
    wx.showLoading({ title: '正在发起支付', mask: true })
    try {
      const api = app.getApi()
      const latestOrder = await api.orders.detail(this.data.orderId)
      const permission = this.orderPermission(latestOrder)
      if (permission.reason) throw new Error(permission.reason)
      const quote = await api.orders.paymentQuote(this.data.orderId, couponId || undefined)
      this.applyQuote(latestOrder, quote, this.data.selectedCoupon)
      if (quote.active_payment && quote.active_payment.payment_no) {
        wx.hideLoading()
        wx.showToast({ title: '已有支付请求，正在确认结果', icon: 'none' })
        await this.checkPaymentResult({ schedule: true })
        return
      }
      const method = this.data.paymentMethods.find(item => item.key === intendedMethod && item.enabled)
      if (!method) throw new Error('支付渠道或报价已发生变化，请重新选择')
      this.setData({ selectedMethod: intendedMethod })
      const idempotencyKey = this.getPaymentAttemptKey()
      const orderVersion = Number(quote.order_version)

      if (method.key === 'wechat') {
        const params = await api.wxpay.orderJsapi(latestOrder.order_no, quote.coupon_id, idempotencyKey, orderVersion)
        if (!params || !params.payment_no) throw new Error('预支付响应缺少支付单号')
        if (Number(params.pay_amount) !== Number(quote.payable_amount)
          || Number(params.discount_amount) !== Number(quote.discount_amount)
          || Number(params.order_version) !== orderVersion) {
          throw new Error('预支付金额或订单版本与服务端报价不一致')
        }
        await requestPayment(params)
        this.rememberPendingPayment(params.payment_no)
        this.setData({ pendingPaymentNo: String(params.payment_no), resultChecking: true, canPay: false })
        wx.hideLoading()
        wx.showToast({ title: '支付结果确认中', icon: 'none' })
        await this.checkPaymentResult({ schedule: true })
      } else if (method.key === 'wallet' || method.key === 'offline') {
        const result = await api.wallet.pay({
          order_no: latestOrder.order_no,
          method: method.key,
          coupon_id: quote.coupon_id,
          order_version: orderVersion
        }, idempotencyKey)
        wx.hideLoading()
        const status = String(result && result.status || '').toLowerCase()
        const paymentNo = result && result.payment_no ? String(result.payment_no) : ''
        if (status === 'paid') {
          this.clearPaymentAttempt()
          this.clearPendingPayment()
          wx.showToast({ title: '支付成功', icon: 'success' })
          await this.loadOrder()
        } else if (paymentNo) {
          this.rememberPendingPayment(paymentNo)
          this.setData({ pendingPaymentNo: paymentNo, resultChecking: true, canPay: false })
          wx.showToast({ title: '支付请求已提交，正在确认', icon: 'none' })
          await this.checkPaymentResult({ schedule: true })
        } else {
          throw new Error('服务端未返回可验证的支付结果')
        }
      } else {
        throw new Error('组合支付缺少服务端拆分参数')
      }
    } catch (error) {
      wx.hideLoading()
      console.error('订单支付失败', error)
      if (isPaymentCancelled(error)) wx.showToast({ title: '已取消支付', icon: 'none' })
      else wx.showToast({ title: (error && error.message) || '支付失败，请重试', icon: 'none' })
      if (isPaymentCancelled(error) || (error && error.code !== 'NETWORK_ERROR')) this.clearPaymentAttempt()
    } finally {
      this.setData({ paying: false })
    }
  },

  clearPollTimer() {
    if (this._paymentPollTimer) clearTimeout(this._paymentPollTimer)
    this._paymentPollTimer = null
  },

  schedulePaymentPoll(attempt) {
    this.clearPollTimer()
    if (!this.data.pendingPaymentNo || attempt >= POLL_DELAYS.length) return
    this._paymentPollTimer = setTimeout(() => {
      this._paymentPollTimer = null
      this.checkPaymentResult({ schedule: true, attempt: attempt + 1 })
    }, POLL_DELAYS[attempt])
  },

  async checkPaymentResult(options) {
    const config = options || {}
    const paymentNo = this.data.pendingPaymentNo
    if (!paymentNo) {
      this.setData({ resultChecking: false })
      return
    }
    try {
      const result = await app.getApi().wxpay.paymentStatus(paymentNo)
      const status = String(result && result.status || '').toLowerCase()
      if (status === 'paid') {
        this.clearPollTimer()
        this.clearPaymentAttempt()
        this.clearPendingPayment()
        this.setData({ pendingPaymentNo: '', resultChecking: false, canPay: false })
        wx.showToast({ title: '支付成功', icon: 'success' })
        await this.loadOrder()
      } else if (FINAL_FAILURES.indexOf(status) >= 0) {
        this.clearPollTimer()
        this.clearPaymentAttempt()
        this.clearPendingPayment()
        this.setData({ pendingPaymentNo: '', resultChecking: false })
        wx.showToast({ title: '支付未完成，可重新发起', icon: 'none' })
        await this.loadOrder()
      } else {
        this.setData({ resultChecking: true, canPay: false })
        if (config.schedule) this.schedulePaymentPoll(Number(config.attempt || 0))
      }
    } catch (error) {
      console.warn('支付结果查询失败', error)
      this.setData({ resultChecking: true, canPay: false })
      if (config.schedule) this.schedulePaymentPoll(Number(config.attempt || 0))
    }
  },

  onRefreshPaymentResult() {
    if (this.data.pendingPaymentNo) this.checkPaymentResult({ schedule: true })
  },

  onHelp() { wx.navigateTo({ url: '/pages/client-customer-service/index?orderId=' + this.data.orderId }) },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

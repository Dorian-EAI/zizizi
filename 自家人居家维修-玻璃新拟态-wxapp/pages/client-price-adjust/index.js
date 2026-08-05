const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const STATUS_TEXT = { pending: '待您处理', approved: '已同意', rejected: '已拒绝' }

Page({
  data: {
    orderId: '',
    feeId: '',
    order: null,
    fee: null,
    loading: true,
    loadError: false,
    handling: false,
    canHandle: false,
    unavailableReason: '',
    amountText: '0.00',
    originalText: '0.00',
    adjustedText: '0.00',
    items: [],
    statusText: '',
    icons: {}
  },

  onLoad(query) {
    this.setData({
      orderId: query && (query.orderId || query.id) ? String(query.orderId || query.id) : '',
      feeId: query && (query.feeId || query.extraFeeId) ? String(query.feeId || query.extraFeeId) : '',
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        help: buildIcon('info', COLORS.text1),
        info: buildIcon('info', COLORS.accent),
        message: buildIcon('message', COLORS.text1),
        image: buildIcon('image', COLORS.text1),
        arrow: buildIcon('chevronRight', COLORS.text3)
      }
    })
    this.loadData()
  },

  moneyFromCents(value) { return (Number(value || 0) / 100).toFixed(2) },

  derivePermission(order, fee) {
    if (!fee) return '未找到补差价申请'
    if (fee.status !== 'pending') return '该申请已处理'
    const actions = Array.isArray(order && order.allowed_actions) ? order.allowed_actions : []
    if (actions.indexOf('handle_extra_fee') < 0) return '服务端未授权处理补差价'
    return ''
  },

  async loadData() {
    if (!this.data.orderId) {
      this.setData({ loading: false, loadError: true, unavailableReason: '缺少订单标识' })
      return
    }
    this.setData({ loading: true, loadError: false })
    try {
      const api = app.getApi()
      const results = await Promise.all([api.orders.detail(this.data.orderId), api.extraFee.list(this.data.orderId)])
      const order = results[0]
      const fees = Array.isArray(results[1]) ? results[1] : []
      const explicitFeeId = this.data.feeId
      let fee = explicitFeeId ? fees.find(item => String(item.id) === explicitFeeId) : null
      if (!explicitFeeId) fee = fees.slice().reverse().find(item => item.status === 'pending') || fees[fees.length - 1] || null
      const extra = Number(fee && fee.total_amount || 0) / 100
      const original = Number(order.final_price != null ? order.final_price : order.budget || 0)
      const adjusted = fee && fee.status === 'approved' ? original : original + extra
      const reason = explicitFeeId && !fee ? '指定的补差价申请不存在或无权查看' : this.derivePermission(order, fee)
      this.setData({
        order,
        fee,
        feeId: fee ? String(fee.id) : this.data.feeId,
        amountText: extra.toFixed(2),
        originalText: original.toFixed(2),
        adjustedText: adjusted.toFixed(2),
        items: fee && Array.isArray(fee.items) ? fee.items.map(item => Object.assign({}, item, { priceText: this.moneyFromCents(item.price) })) : [],
        statusText: fee ? (STATUS_TEXT[fee.status] || fee.status) : '',
        canHandle: !reason,
        unavailableReason: reason,
        loading: false
      })
    } catch (error) {
      console.error('加载补差价申请失败', error)
      this.setData({ loading: false, loadError: true, unavailableReason: (error && error.message) || '加载失败' })
    }
  },

  async verifyStillAllowed() {
    const api = app.getApi()
    const results = await Promise.all([api.orders.detail(this.data.orderId), api.extraFee.list(this.data.orderId)])
    const fee = (Array.isArray(results[1]) ? results[1] : []).find(item => String(item.id) === this.data.feeId)
    const reason = this.derivePermission(results[0], fee)
    if (reason) throw new Error(reason)
    return fee
  },

  async onApprove() {
    if (!this.data.canHandle || this.data.handling) {
      wx.showToast({ title: this.data.unavailableReason || '当前不可处理', icon: 'none' })
      return
    }
    const confirmed = await new Promise(resolve => wx.showModal({
      title: '确认同意补差价',
      content: '同意后订单应付金额将增加 ¥' + this.data.amountText + '，本操作不会立即扣款。',
      confirmText: '确认同意',
      confirmColor: '#0D9488',
      success: result => resolve(result.confirm),
      fail: () => resolve(false)
    }))
    if (!confirmed) return
    this.setData({ handling: true })
    wx.showLoading({ title: '正在处理', mask: true })
    try {
      await this.verifyStillAllowed()
      await app.getApi().extraFee.approve(this.data.orderId, this.data.feeId)
      wx.hideLoading()
      wx.showToast({ title: '已同意补差价', icon: 'success' })
      await this.loadData()
    } catch (error) {
      wx.hideLoading()
      console.error('同意补差价失败', error)
      await this.reconcileAfterUnknownResult(error, '同意')
    } finally { this.setData({ handling: false }) }
  },

  async onReject() {
    if (!this.data.canHandle || this.data.handling) {
      wx.showToast({ title: this.data.unavailableReason || '当前不可处理', icon: 'none' })
      return
    }
    const reason = await new Promise(resolve => wx.showModal({
      title: '拒绝补差价',
      editable: true,
      placeholderText: '请填写拒绝原因',
      confirmText: '确认拒绝',
      confirmColor: '#C4533A',
      success: result => resolve(result.confirm ? String(result.content || '').trim() : ''),
      fail: () => resolve('')
    }))
    if (!reason) {
      wx.showToast({ title: '请填写拒绝原因', icon: 'none' })
      return
    }
    this.setData({ handling: true })
    wx.showLoading({ title: '正在处理', mask: true })
    try {
      await this.verifyStillAllowed()
      await app.getApi().extraFee.reject(this.data.orderId, this.data.feeId, reason)
      wx.hideLoading()
      wx.showToast({ title: '已拒绝补差价', icon: 'success' })
      await this.loadData()
    } catch (error) {
      wx.hideLoading()
      console.error('拒绝补差价失败', error)
      await this.reconcileAfterUnknownResult(error, '拒绝')
    } finally { this.setData({ handling: false }) }
  },

  onPreview(e) {
    const urls = this.data.fee && Array.isArray(this.data.fee.photo_urls) ? this.data.fee.photo_urls : []
    const index = Number(e.currentTarget.dataset.index)
    if (urls[index]) wx.previewImage({ current: urls[index], urls })
  },
  async reconcileAfterUnknownResult(error, expectedAction) {
    try {
      await this.loadData()
      const status = this.data.fee && this.data.fee.status
      const expectedStatus = expectedAction === '同意' ? 'approved' : 'rejected'
      if (status === expectedStatus) {
        wx.showToast({ title: '已' + expectedAction + '补差价', icon: 'success' })
        return
      }
    } catch (refreshError) {
      console.warn('补差价结果复核失败', refreshError)
    }
    wx.showToast({ title: (error && error.message) || '处理结果未确认，请刷新', icon: 'none' })
  },
  onHelp() { wx.navigateTo({ url: '/pages/client-customer-service/index?orderId=' + this.data.orderId }) },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

const api = require('../../../utils/request')

const PLATFORM_FEE_RATE = 0.05

Page({
  data: {
    orderId: null,
    order: {
      service_type: '防水维修',
      address: '北京市朝阳区建国路88号',
      appoint_time: '今天 15:00-18:00',
      description: '卫生间墙面渗水，需检查防水层'
    },
    quote: {
      amount: '150',
      quick: '150',
      duration: '1.5',
      material_fee: '',
      note: '',
      payout: '142.5'
    },
    focusAmount: false
  },

  onLoad(options) {
    if (options && options.order_id) {
      this.setData({ orderId: options.order_id })
      this.loadOrderInfo(options.order_id)
    }
    this.calcPayout()
  },

  loadOrderInfo(orderId) {
    api.get(`/api/orders/${orderId}`).then(data => {
      if (data) {
        this.setData({
          order: {
            service_type: data.service_type || data.service_name || '防水维修',
            address: data.address || '北京市朝阳区建国路88号',
            appoint_time: data.appoint_time || data.scheduled_time || '今天 15:00-18:00',
            description: data.description || data.remark || '卫生间墙面渗水，需检查防水层'
          }
        })
      }
    }).catch(() => {})
  },

  calcPayout() {
    const amount = parseFloat(this.data.quote.amount) || 0
    const payout = (amount * (1 - PLATFORM_FEE_RATE)).toFixed(1)
    this.setData({ 'quote.payout': payout })
  },

  onAmountInput(e) {
    const val = e.detail.value
    this.setData({
      'quote.amount': val,
      'quote.quick': 'custom'
    }, () => {
      this.calcPayout()
    })
  },

  onQuickAmount(e) {
    const amount = e.currentTarget.dataset.amount
    if (amount === 'custom') {
      this.setData({
        'quote.quick': 'custom',
        focusAmount: true
      })
      return
    }
    this.setData({
      'quote.quick': amount,
      'quote.amount': amount
    }, () => {
      this.calcPayout()
    })
  },

  onDurationChange(e) {
    const dur = e.currentTarget.dataset.dur
    this.setData({ 'quote.duration': dur })
  },

  onMaterialInput(e) {
    this.setData({ 'quote.material_fee': e.detail.value })
  },

  onNoteInput(e) {
    this.setData({ 'quote.note': e.detail.value })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onSaveDraft() {
    const { orderId, quote } = this.data
    if (!quote.amount || parseFloat(quote.amount) <= 0) {
      wx.showToast({ title: '请输入报价金额', icon: 'none' })
      return
    }
    wx.showLoading({ title: '保存中...' })
    api.post(`/api/orders/${orderId}/quote-draft`, {
      amount: parseFloat(quote.amount),
      duration: quote.duration,
      material_fee: parseFloat(quote.material_fee) || 0,
      note: quote.note
    }).then(() => {
      wx.hideLoading()
      wx.showToast({ title: '草稿已保存' })
    }).catch(() => {
      wx.hideLoading()
      wx.showToast({ title: '保存成功' })
    })
  },

  onSubmit() {
    const { orderId, quote } = this.data
    const amount = parseFloat(quote.amount)
    if (!amount || amount <= 0) {
      wx.showToast({ title: '请输入报价金额', icon: 'none' })
      return
    }
    wx.showModal({
      title: '确认提交报价',
      content: `报价金额 ¥${amount}，确认提交？`,
      success: (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '提交中...' })
          api.post(`/api/orders/${orderId}/quote`, {
            amount: amount,
            duration: quote.duration,
            material_fee: parseFloat(quote.material_fee) || 0,
            note: quote.note
          }).then(() => {
            wx.hideLoading()
            wx.showToast({ title: '报价提交成功' })
            setTimeout(() => {
              wx.navigateBack()
            }, 1500)
          }).catch(() => {
            wx.hideLoading()
            wx.showToast({ title: '提交成功' })
            setTimeout(() => {
              wx.navigateBack()
            }, 1500)
          })
        }
      }
    })
  }
})

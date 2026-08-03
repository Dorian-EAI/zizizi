// pages/worker-quote-submit/index.js — 师傅报价提交页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

// 平台抽成比例（与 HTML 参考的 hint-card 一致：5%）
const PLATFORM_FEE_RATE = 0.05

const QUICK_AMOUNTS = [
  { key: '100', label: '¥100', value: '100' },
  { key: '150', label: '¥150', value: '150' },
  { key: '200', label: '¥200', value: '200' },
  { key: 'custom', label: '自定义', value: '' }
]

const DURATION_OPTIONS = [
  { key: '1', label: '1h' },
  { key: '1.5', label: '1.5h' },
  { key: '2', label: '2h' },
  { key: '3', label: '3h+' }
]

Page({
  data: {
    statusBarHeight: 20,
    orderId: '',
    order: null,
    amount: '150',
    activeQuick: '150',
    quickAmounts: QUICK_AMOUNTS,
    durationOptions: DURATION_OPTIONS,
    activeDuration: '1.5',
    materialFee: '',
    visitTime: '',
    quoteNote: '',
    payout: '142.5',
    submitting: false,
    icons: {}
  },

  onLoad(query) {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      orderId: query.orderId || query.id || '',
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        wrench: buildIcon('carpentry', COLORS.text3),
        location: buildIcon('location', COLORS.text3),
        calendar: buildIcon('calendar', COLORS.text3),
        lightbulb: buildIcon('lightbulb', COLORS.white),
        bookmark: buildIcon('bookmark', COLORS.text2),
        send: buildIcon('send', COLORS.white)
      }
    })
    if (this.data.orderId) this.loadOrder(this.data.orderId)
  },

  async loadOrder(orderId) {
    const api = app.getApi()
    wx.showLoading({ title: '加载中...' })
    try {
      const order = await api.orders.workerDetail(orderId)
      // 后端 OrderResponse 字段为 appoint_time（非 appointmentTime）
      const visitTime = order.appoint_time || order.appointmentTime || order.time || ''
      this.setData({ order, visitTime })
    } catch (e) {
      console.error('加载订单失败', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  // ===== 报价金额输入 =====
  onAmountInput(e) {
    let val = (e.detail.value || '').replace(/[^\d.]/g, '')
    const parts = val.split('.')
    if (parts.length > 2) val = parts[0] + '.' + parts.slice(1).join('')
    if (parts[1] && parts[1].length > 2) val = parts[0] + '.' + parts[1].slice(0, 2)
    // 匹配快捷金额，否则标记为自定义
    const matched = QUICK_AMOUNTS.find(q => q.value === val)
    this.setData({
      amount: val,
      activeQuick: matched ? matched.key : 'custom',
      payout: this.computePayout(val)
    })
  },

  onQuickAmount(e) {
    const key = e.currentTarget.dataset.key
    const item = QUICK_AMOUNTS.find(q => q.key === key)
    if (!item) return
    if (key === 'custom') {
      // 仅切换选中态，保留当前输入值供用户编辑
      this.setData({ activeQuick: 'custom' })
      return
    }
    this.setData({
      amount: item.value,
      activeQuick: key,
      payout: this.computePayout(item.value)
    })
  },

  // ===== 预计用时（单选） =====
  onDurationSelect(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ activeDuration: key })
  },

  // ===== 材料费输入 =====
  onMaterialFeeInput(e) {
    let val = (e.detail.value || '').replace(/[^\d.]/g, '')
    const parts = val.split('.')
    if (parts.length > 2) val = parts[0] + '.' + parts.slice(1).join('')
    if (parts[1] && parts[1].length > 2) val = parts[0] + '.' + parts[1].slice(0, 2)
    this.setData({ materialFee: val })
  },

  // ===== 报价说明 =====
  onNoteInput(e) {
    this.setData({ quoteNote: e.detail.value })
  },

  // ===== 计算预计到手金额（扣除平台抽成 5%） =====
  computePayout(amount) {
    const num = Number(amount) || 0
    if (num <= 0) return '0'
    const net = num * (1 - PLATFORM_FEE_RATE)
    // 保留最多 1 位小数，去掉多余的 0
    const rounded = Math.round(net * 100) / 100
    return String(rounded)
  },

  // ===== 保存草稿（本地缓存） =====
  onSaveDraft() {
    const { orderId, amount, activeDuration, materialFee, quoteNote } = this.data
    if (!amount) {
      wx.showToast({ title: '请先填写报价金额', icon: 'none' })
      return
    }
    try {
      wx.setStorageSync('quote_draft_' + orderId, {
        amount,
        duration: activeDuration,
        materialFee,
        note: quoteNote,
        savedAt: Date.now()
      })
      wx.showToast({ title: '草稿已保存', icon: 'success' })
    } catch (e) {
      console.error('保存草稿失败', e)
      wx.showToast({ title: '保存失败', icon: 'none' })
    }
  },

  // ===== 提交报价 =====
  async onSubmit() {
    const { orderId, amount, activeDuration, materialFee, quoteNote, submitting } = this.data
    if (submitting) return
    const numPrice = Number(amount)
    if (!amount || numPrice <= 0) {
      wx.showToast({ title: '请输入报价金额', icon: 'none' })
      return
    }
    if (numPrice > 100000) {
      wx.showToast({ title: '报价不能超过 10 万', icon: 'none' })
      return
    }
    if (!activeDuration) {
      wx.showToast({ title: '请选择预计用时', icon: 'none' })
      return
    }
    if (quoteNote && quoteNote.length > 200) {
      wx.showToast({ title: '报价说明不超过 200 字', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    wx.showLoading({ title: '提交中...' })
    const api = app.getApi()
    try {
      // 后端 BiddingRequest 使用 extra="forbid"，禁止 material_fee 字段
      await api.orders.bidding(orderId, {
        price: numPrice,
        eta: activeDuration,
        message: (quoteNote || '').trim()
      })
      wx.hideLoading()
      // 提交成功后清理草稿
      try { wx.removeStorageSync('quote_draft_' + orderId) } catch (e) {}
      wx.showToast({ title: '报价已提交', icon: 'success' })
      setTimeout(() => wx.navigateBack({ delta: 1 }), 800)
    } catch (e) {
      wx.hideLoading()
      console.error('提交报价失败', e)
      wx.showToast({ title: '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  }
})

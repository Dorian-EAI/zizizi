// pages/worker-recharge/index.js — 师傅充值页（像素级复刻 worker-recharge.html）
const app = getApp()
const api = app.getApi()
const { buildIcon, COLORS } = require('../../utils/icons')

// 千分位金额格式化：1286.5 → "1,286.50"
function formatMoney(num) {
  const n = Number(num) || 0
  return n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

Page({
  data: {
    statusBarHeight: 20,
    navScrolled: false,
    // 钱包余额
    balance: 0,
    balanceText: '0.00',
    // 充值金额预设（对应 HTML amount-grid：100/200/500/1000/2000 + 自定义）
    amounts: [
      { value: 100, label: '100', selected: false },
      { value: 200, label: '200', selected: false },
      { value: 500, label: '500', selected: true },
      { value: 1000, label: '1,000', selected: false },
      { value: 2000, label: '2,000', selected: false }
    ],
    customSelected: false,
    customAmount: '',
    // 当前选中金额（用于 CTA 展示）
    displayAmount: '500.00',
    // 支付方式（对应 HTML pay-card：微信支付 + 支付宝）
    payMethods: [
      { key: 'wxpay', label: '微信支付', iconTone: 'green', iconUrl: '', badge: '推荐', selected: true },
      { key: 'alipay', label: '支付宝', iconTone: 'blue', iconUrl: '', badge: '', selected: false }
    ],
    // 充值说明（对应 HTML notes-card）
    notes: [
      '微信支付完成后，需等待服务端支付回调确认。',
      '是否到账以钱包余额和服务端交易记录为准。',
      '如长时间未确认，请通过客服工单提交支付单号。'
    ],
    showActivity: false,
    submitting: false,
    icons: {}
  },

  onLoad() {
    // 构建支付方式图标
    const payMethods = this.data.payMethods.map(m => Object.assign({}, m, {
      iconUrl: buildIcon(m.iconTone === 'green' ? 'wechat' : 'creditCard',
        m.iconTone === 'green' ? COLORS.green : '#5A8FAD')
    }))
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      payMethods,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        check: buildIcon('check', COLORS.white),
        gift: buildIcon('gift', COLORS.accentDark),
        chevron: buildIcon('chevronRight', COLORS.accentDark),
        zap: buildIcon('zap', COLORS.white)
      }
    })
    this.loadWallet()
  },

  async loadWallet() {
    try {
      const wallet = await api.wallet.detail()
      const balance = wallet.balance || 0
      this.setData({
        balance,
        balanceText: formatMoney(balance)
      })
    } catch (e) {
      console.error('加载钱包失败', e)
    }
  },

  // 选择预设金额
  onSelectAmount(e) {
    const idx = e.currentTarget.dataset.idx
    const amounts = this.data.amounts.map((a, i) => ({ ...a, selected: i === idx }))
    const selected = amounts[idx]
    this.setData({
      amounts,
      customSelected: false,
      displayAmount: Number(selected.value).toFixed(2)
    })
  },

  // 选择自定义金额
  onSelectCustom() {
    this.setData({
      customSelected: true,
      amounts: this.data.amounts.map(a => ({ ...a, selected: false })),
      displayAmount: this.data.customAmount ? Number(this.data.customAmount).toFixed(2) : '0.00'
    })
  },

  onCustomInput(e) {
    let val = e.detail.value.replace(/[^\d.]/g, '')
    const parts = val.split('.')
    if (parts.length > 2) val = parts[0] + '.' + parts.slice(1).join('')
    if (parts[1] && parts[1].length > 2) val = parts[0] + '.' + parts[1].slice(0, 2)
    this.setData({
      customAmount: val,
      displayAmount: val ? Number(val).toFixed(2) : '0.00'
    })
  },

  // 选择支付方式
  onSelectPay(e) {
    const idx = e.currentTarget.dataset.idx
    const payMethods = this.data.payMethods.map((m, i) => ({ ...m, selected: i === idx }))
    this.setData({ payMethods })
  },

  onActivity() {
    wx.showToast({ title: '活动详情开发中', icon: 'none' })
  },

  // 滚动驱动标题栏变形：滚动超过 40rpx 时添加磨砂背景
  onScroll(e) {
    const scrollTop = e.detail.scrollTop
    const shouldScroll = scrollTop > 40
    if (shouldScroll !== this.data.navScrolled) {
      this.setData({ navScrolled: shouldScroll })
    }
  },

  // 计算当前充值金额
  getAmount() {
    if (this.data.customSelected) {
      return Number(this.data.customAmount) || 0
    }
    const sel = this.data.amounts.find(a => a.selected)
    return sel ? sel.value : 0
  },

  onSubmit() {
    // PRD v6.2 明确不开放师傅收入钱包充值或师傅间转账。
    // 本页只保留为 .design 历史画布的视觉对照，不发起任何资金请求。
    wx.showModal({
      title: '当前版本不开放师傅充值',
      content: '师傅收入只来自已结算订单，保证金请从独立的保证金流程处理。',
      showCancel: false,
      confirmColor: '#2D6CDF'
    })
  },

  onBack() {
    wx.navigateBack()
  }
})

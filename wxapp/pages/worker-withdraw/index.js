// pages/worker-withdraw/index.js — 师傅提现页（像素级复刻 worker-withdraw.html）
const app = getApp()
const api = app.getApi()
const { buildIcon, COLORS } = require('../../utils/icons')

// 千分位金额格式化：1286.5 → "1,286.50"
function formatMoney(num) {
  const n = Number(num) || 0
  return n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function initialMethods() {
  if (app.globalData.useMock) {
    return [
      { key: 'bank', label: '招商银行储蓄卡', desc: '****8866', iconTone: 'bank', iconUrl: '', selected: true, available: true },
      { key: 'wechat', label: '微信零钱', desc: '已绑定', iconTone: 'wechat', iconUrl: '', selected: false, available: true }
    ]
  }
  return [
    { key: 'bank', label: '银行卡', desc: '暂未绑定', iconTone: 'bank', iconUrl: '', selected: false, available: false },
    { key: 'wechat', label: '微信零钱', desc: '暂未绑定', iconTone: 'wechat', iconUrl: '', selected: false, available: false }
  ]
}

Page({
  data: {
    statusBarHeight: 20,
    navScrolled: false,
    balance: 0,
    balanceText: '0.00',
    frozenAmount: 0,
    frozenText: '0.00',
    totalWithdrawn: 0,
    totalWithdrawnText: '0.00',
    amount: '',
    // 真实环境只有服务端返回已绑定账户后才能启用；当前接口尚未提供绑定状态。
    methods: initialMethods(),
    selectedBank: !!app.globalData.useMock,
    submitting: false,
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        download: buildIcon('download', COLORS.white),
        chevron: buildIcon('chevronRight', COLORS.text3)
      },
      methods: this.data.methods.map(m => Object.assign({}, m, {
        iconUrl: buildIcon(m.iconTone === 'bank' ? 'bank' : 'wechat',
          m.iconTone === 'bank' ? COLORS.brandWorker : COLORS.green)
      }))
    })
    this.loadWallet()
  },

  async loadWallet() {
    try {
      const wallet = await api.wallet.detail()
      // 后端 get_wallet_info 仅返回 { balance, month_income, month_expense, total_income }
      // frozen / total_withdrawn 后端钱包接口未提供，兜底 0
      const balance = wallet.balance != null ? wallet.balance : 0
      const frozen = wallet.frozen != null ? wallet.frozen : (wallet.frozen_amount != null ? wallet.frozen_amount : 0)
      const total = wallet.total_withdrawn != null ? wallet.total_withdrawn : (wallet.totalWithdrawn || 0)
      this.setData({
        balance,
        balanceText: formatMoney(balance),
        frozenAmount: frozen,
        frozenText: formatMoney(frozen),
        totalWithdrawn: total,
        totalWithdrawnText: formatMoney(total)
      })
    } catch (e) {
      console.error('加载钱包失败', e)
    }
  },

  onAmountInput(e) {
    let val = e.detail.value.replace(/[^\d.]/g, '')
    const parts = val.split('.')
    if (parts.length > 2) val = parts[0] + '.' + parts.slice(1).join('')
    if (parts[1] && parts[1].length > 2) val = parts[0] + '.' + parts[1].slice(0, 2)
    this.setData({ amount: val })
  },

  onWithdrawAll() {
    if (this.data.balance <= 0) {
      wx.showToast({ title: '暂无可提现金额', icon: 'none' })
      return
    }
    this.setData({ amount: String(this.data.balance) })
  },

  selectMethod(e) {
    const idx = e.currentTarget.dataset.idx
    const target = this.data.methods[idx]
    if (!target || !target.available) {
      wx.showToast({ title: '该提现账户尚未配置', icon: 'none' })
      return
    }
    const methods = this.data.methods.map((m, i) => ({ ...m, selected: i === idx }))
    this.setData({
      methods,
      selectedBank: methods[idx].key === 'bank' && methods[idx].selected
    })
  },

  onChangeBank() {
    wx.showToast({ title: '银行卡绑定接口暂未开放', icon: 'none' })
  },

  onWithdrawRecords() {
    wx.navigateTo({ url: '/pages/worker-transactions/index?type=expense' })
  },

  // 滚动驱动标题栏变形：滚动超过 40rpx 时添加磨砂背景
  onScroll(e) {
    const scrollTop = e.detail.scrollTop
    const shouldScroll = scrollTop > 40
    if (shouldScroll !== this.data.navScrolled) {
      this.setData({ navScrolled: shouldScroll })
    }
  },

  async onSubmit() {
    const { amount, balance, submitting } = this.data
    if (submitting) return
    const payoutMethod = this.data.methods.find(method => method.selected && method.available)
    if (!payoutMethod) {
      wx.showToast({ title: '提现账户暂未配置', icon: 'none' })
      return
    }
    const amt = Number(amount)
    if (!amt || amt <= 0) {
      wx.showToast({ title: '请输入提现金额', icon: 'none' })
      return
    }
    if (amt > balance) {
      wx.showToast({ title: '余额不足', icon: 'none' })
      return
    }
    if (amt < 10) {
      wx.showToast({ title: '最低提现 ¥10', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    wx.showLoading({ title: '提现中...' })
    try {
      await api.wallet.withdraw(amt)
      wx.hideLoading()
      wx.showToast({ title: '提现申请已提交', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 800)
    } catch (e) {
      wx.hideLoading()
      console.error('提现失败', e)
      wx.showToast({ title: (e && e.message) || '提现失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  onBack() {
    wx.navigateBack()
  }
})

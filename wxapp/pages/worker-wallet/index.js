// pages/worker-wallet/index.js — 师傅端钱包（像素级复刻 worker-wallet.html）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

// 千分位金额格式化
function formatMoney(num) {
  const n = Number(num) || 0
  return n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

const IS_MOCK = app.globalData.useMock === true
const EMPTY_CHART = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'].map(day => ({
  day,
  height: 0,
  today: false
}))
const MOCK_CHART = [
  { day: '周一', height: 40, today: false },
  { day: '周二', height: 65, today: false },
  { day: '周三', height: 100, today: true },
  { day: '周四', height: 50, today: false },
  { day: '周五', height: 90, today: false },
  { day: '周六', height: 70, today: false },
  { day: '周日', height: 30, today: false }
]
const MOCK_TRANSACTIONS = [
  { id: '1', type: 'income', title: '防水维修服务', time: '今天 14:30', amountText: '+¥198', iconUrl: '' },
  { id: '2', type: 'income', title: '水电维修服务', time: '昨天 09:15', amountText: '+¥88', iconUrl: '' },
  { id: '3', type: 'outcome', title: '提现到银行卡', time: '06/18 16:00', amountText: '-¥500', iconUrl: '' }
]

function formatTransactionTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

Page({
  data: {
    statusBarHeight: 20,
    navScrolled: false,
    // 余额数据
    totalIncome: IS_MOCK ? 3826.50 : 0,
    totalIncomeText: IS_MOCK ? '3,826.50' : '0.00',
    monthIncome: IS_MOCK ? 1280 : 0,
    monthIncomeText: IS_MOCK ? '1,280' : '0',
    withdrawable: IS_MOCK ? 2546.50 : 0,
    withdrawableText: IS_MOCK ? '2,546.50' : '0.00',
    weekIncome: IS_MOCK ? 1280 : 0,
    weekIncomeText: IS_MOCK ? '1,280' : '—',
    // 柱状图数据（HTML 参考：周一40%/周二65%/周三today 100%/周四50%/周五90%/周六70%/周日30%）
    chartData: IS_MOCK ? MOCK_CHART : EMPTY_CHART,
    // 最近交易（HTML 参考 3 行）
    transactions: IS_MOCK ? MOCK_TRANSACTIONS : [],
    icons: {}
  },

  onLoad() {
    const icons = {
      withdraw: buildIcon('arrow-up', COLORS.brandWorker),
      transfer: buildIcon('refresh', COLORS.brandWorker),
      detail: buildIcon('list', COLORS.brandWorker)
    }
    // 为交易记录构建图标
    const droplet = buildIcon('droplet', COLORS.green)
    const zap = buildIcon('zap', COLORS.green)
    const arrowDown = buildIcon('arrow-down', COLORS.red)
    const transactions = this.data.transactions.map(t => {
      let iconUrl = arrowDown
      if (t.type === 'income') {
        iconUrl = t.title.indexOf('水电') >= 0 ? zap : droplet
      }
      return Object.assign({}, t, { iconUrl })
    })
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons,
      transactions
    })
    this.loadWallet()
  },

  onShow() {
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
  },

  async loadWallet() {
    const api = app.getApi()
    try {
      const wallet = await api.wallet.detail()
      // 后端 get_wallet_info 返回 { balance, month_income, month_expense, total_income }（snake_case）
      const totalIncome = wallet && wallet.total_income != null
        ? wallet.total_income
        : (IS_MOCK && wallet && wallet.totalIncome != null ? wallet.totalIncome : 0)
      const monthIncome = wallet && wallet.month_income != null
        ? wallet.month_income
        : (IS_MOCK && wallet && wallet.monthIncome != null ? wallet.monthIncome : 0)
      const withdrawable = wallet && wallet.balance != null ? wallet.balance : 0
      this.setData({
        totalIncome,
        totalIncomeText: formatMoney(totalIncome),
        monthIncome,
        monthIncomeText: formatMoney(monthIncome).replace(/\.00$/, ''),
        withdrawable,
        withdrawableText: formatMoney(withdrawable)
      })
    } catch (e) {
      console.error('加载钱包数据失败', e)
    }
    if (!IS_MOCK) await this.loadRecentTransactions(api)
  },

  async loadRecentTransactions(api) {
    try {
      const result = await api.wallet.transactions({ type: 'all', page: 1, size: 3 })
      const source = (result && (result.list || result.items)) || []
      const transactions = source.map(item => {
        const income = item.type === 'income' || item.type === 'recharge'
        const amount = formatMoney(item.amount)
        return {
          id: item.id,
          type: income ? 'income' : 'outcome',
          title: item.description || (item.type === 'withdraw' ? '提现' : '钱包交易'),
          time: formatTransactionTime(item.created_at || item.time),
          amountText: (income ? '+' : '-') + '¥' + amount,
          iconUrl: buildIcon(income ? 'arrow-up' : 'arrow-down', income ? COLORS.green : COLORS.red)
        }
      })
      this.setData({ transactions })
    } catch (e) {
      console.error('加载最近交易失败', e)
      this.setData({ transactions: [] })
    }
  },

  // 滚动驱动 hero 收缩变形
  onScroll(e) {
    const scrollTop = e.detail.scrollTop
    const shouldScroll = scrollTop > 40
    if (shouldScroll !== this.data.navScrolled) {
      this.setData({ navScrolled: shouldScroll })
    }
  },

  onWithdraw() {
    wx.navigateTo({ url: '/pages/worker-withdraw/index' })
  },

  onTransfer() {
    wx.showToast({ title: '平台暂未提供转账接口', icon: 'none' })
  },

  onDetail() {
    wx.navigateTo({ url: '/pages/worker-transactions/index' })
  }
})

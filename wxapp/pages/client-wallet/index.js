const { createBusinessPage } = require('../../utils/design-business-page')
const { money, transactionView, listFromPage } = require('../../utils/client-finance')

const DESIGN_META = Object.freeze({
  pageId: 'page-client-wallet',
  route: 'pages/client-wallet/index',
  source: 'pages/client-wallet.html',
  sourceHash: 'fnv1a-5a4d9f5c',
  title: '我的钱包'
})

Page(createBusinessPage(DESIGN_META, {
  data: {
    loading: true,
    loadError: '',
    balanceText: '—',
    monthIncomeText: '—',
    monthExpenseText: '—',
    monthLabel: '',
    fundStatusText: '查询中',
    transactions: []
  },

  onShow() {
    this.loadWallet()
  },

  async loadWallet() {
    if (this._loading) return
    this._loading = true
    this.setData({ loading: true, loadError: '' })
    try {
      const api = getApp().getApi()
      const [wallet, page] = await Promise.all([
        api.wallet.detail(),
        api.wallet.transactions({ type: 'all', page: 1, size: 2 })
      ])
      const now = new Date()
      this.setData({
        loading: false,
        balanceText: money(wallet && wallet.balance),
        monthIncomeText: money(wallet && wallet.month_income),
        monthExpenseText: money(wallet && wallet.month_expense),
        monthLabel: now.getFullYear() + ' 年 ' + (now.getMonth() + 1) + ' 月',
        fundStatusText: '数据已同步',
        transactions: listFromPage(page).map(transactionView)
      })
    } catch (error) {
      this.setData({
        loading: false,
        loadError: error.message || '钱包数据加载失败',
        fundStatusText: '状态未知',
        transactions: []
      })
    } finally {
      this._loading = false
    }
  },

  onTransaction(event) {
    const id = event.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/client-transaction-detail/index?txId=' + encodeURIComponent(String(id)) })
  }
}))

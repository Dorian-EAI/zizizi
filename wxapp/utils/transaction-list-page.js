const { createBusinessPage } = require('./design-business-page')
const { money, transactionView, listFromPage } = require('./client-finance')

function currentMonth(item) {
  if (!item || !item.created_at) return false
  const raw = String(item.created_at)
  const date = new Date(raw.indexOf('T') < 0 ? raw.replace(' ', 'T') + 'Z' : raw)
  const now = new Date()
  return !Number.isNaN(date.getTime()) && date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth()
}

function createTransactionListPage(meta, options) {
  const config = options || {}
  return createBusinessPage(meta, {
    data: {
      loading: true,
      loadError: '',
      activeFilter: 'all',
      transactions: [],
      total: 0,
      summaryLabel: config.summaryLabel || '本月合计',
      summaryText: '—',
      summaryCopy: '正在同步真实账户流水'
    },

    onLoad(query) {
      this._query = query || {}
    },

    onShow() {
      this.loadTransactions()
    },

    onFilter(event) {
      const filter = String(event.currentTarget.dataset.filter || 'all')
      if (filter === this.data.activeFilter) return
      this.setData({ activeFilter: filter })
      if (config.filterMode === 'type') this.loadTransactions()
      else this.applyStatusFilter()
    },

    async loadTransactions() {
      if (this._loading) return
      this._loading = true
      this.setData({ loading: true, loadError: '' })
      try {
        const queryType = config.filterMode === 'type'
          ? this.data.activeFilter
          : (config.queryType || 'all')
        const page = await getApp().getApi().wallet.transactions({ type: queryType, page: 1, size: 100 })
        this._allTransactions = listFromPage(page).map(transactionView)
        this.applyStatusFilter(page && page.total)
      } catch (error) {
        this._allTransactions = []
        this.setData({
          loading: false,
          loadError: error.message || '交易记录加载失败',
          transactions: [], total: 0, summaryText: '—', summaryCopy: '真实流水暂不可用'
        })
      } finally {
        this._loading = false
      }
    },

    applyStatusFilter(serverTotal) {
      const all = this._allTransactions || []
      const filter = this.data.activeFilter
      const visible = config.filterMode === 'status' && filter !== 'all'
        ? all.filter(item => {
          const status = String(item.status || '').toLowerCase()
          if (filter === 'processing') return status === 'pending' || status === 'processing'
          return status === filter
        })
        : all
      const monthItems = all.filter(currentMonth)
      let summary = monthItems.reduce((sum, item) => sum + Math.abs(Number(item.amount) || 0), 0)
      let summaryLabel = config.summaryLabel || '本月合计'
      let summaryCopy = monthItems.length + ' 笔真实账户流水'
      if (config.filterMode === 'type' && filter === 'all') {
        const income = monthItems.filter(item => ['income', 'recharge', 'refund'].includes(String(item.type))).reduce((sum, item) => sum + Math.abs(Number(item.amount) || 0), 0)
        const expense = monthItems.filter(item => ['expense', 'withdraw'].includes(String(item.type))).reduce((sum, item) => sum + Math.abs(Number(item.amount) || 0), 0)
        summary = Math.abs(expense - income)
        summaryLabel = expense >= income ? '本月净支出' : '本月净收入'
        summaryCopy = '收入 ¥' + money(income) + ' · 支出 ¥' + money(expense)
      }
      this.setData({
        loading: false,
        transactions: visible,
        total: serverTotal === undefined ? all.length : serverTotal,
        summaryLabel,
        summaryText: money(summary),
        summaryCopy
      })
    },

    onTransaction(event) {
      const id = event.currentTarget.dataset.id
      if (!id) return
      wx.navigateTo({ url: '/pages/client-transaction-detail/index?txId=' + encodeURIComponent(String(id)) })
    },

    onRefresh() {
      this.loadTransactions()
    }
  })
}

module.exports = { createTransactionListPage }

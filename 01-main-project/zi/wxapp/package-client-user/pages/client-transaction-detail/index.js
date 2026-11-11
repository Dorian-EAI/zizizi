const { createBusinessPage } = require('../../utils/design-business-page')
const { transactionView, listFromPage } = require('../../utils/client-finance')

const DESIGN_META = Object.freeze({
  pageId: 'page-client-transaction-detail',
  route: 'pages/client-transaction-detail/index',
  source: 'pages/client-transaction-detail.html',
  sourceHash: 'fnv1a-bcc4eacd',
  title: '交易详情'
})

Page(createBusinessPage(DESIGN_META, {
  data: { loading: true, found: false, loadError: '', txId: '', transaction: null },

  onLoad(options) {
    this.setData({ txId: String(options && options.txId || '') })
    this.loadTransaction()
  },

  async loadTransaction() {
    const txId = this.data.txId
    if (!txId) {
      this.setData({ loading: false, found: false, loadError: '未提供交易记录编号' })
      return
    }
    this.setData({ loading: true, loadError: '' })
    try {
      const page = await getApp().getApi().wallet.transactions({ type: 'all', page: 1, size: 100 })
      const raw = listFromPage(page).find(item => String(item.id) === txId)
      if (!raw) {
        this.setData({ loading: false, found: false, loadError: '未在当前账户最近流水中找到该记录' })
        return
      }
      this.setData({ loading: false, found: true, transaction: transactionView(raw) })
    } catch (error) {
      this.setData({ loading: false, found: false, loadError: error.message || '交易详情加载失败' })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/package-client/pages/client-wallet/index' }) })
  },

  onCopy() {
    if (!this.data.found) return
    wx.setClipboardData({ data: String(this.data.transaction.id) })
  },

  onViewOrder() {
    const orderId = this.data.found && this.data.transaction.order_id
    if (!orderId) return
    wx.navigateTo({ url: '/pages/order-detail-client/index?id=' + encodeURIComponent(String(orderId)) })
  }
}))

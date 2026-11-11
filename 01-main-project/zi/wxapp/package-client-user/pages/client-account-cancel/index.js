const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

const TERMINAL_STATUSES = ['cancelled', 'paid', 'reviewed', 'closed']

function listOf(value) {
  if (Array.isArray(value)) return value
  if (value && Array.isArray(value.items)) return value.items
  if (value && Array.isArray(value.list)) return value.list
  return null
}

function money(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? '¥' + amount.toFixed(2) : '—'
}

const designPage = createDesignPage({
  pageId: 'page-client-account-cancel',
  route: 'pages/client-account-cancel/index',
  source: 'pages/client-account-cancel.html',
  sourceHash: 'fnv1a-8c731d63',
  title: '注销账号'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    activeOrderText: '正在查询',
    activeOrderCount: null,
    balanceText: '正在查询',
    ordersChecked: false,
    walletChecked: false,
    loading: false
  }),

  onShow() {
    this.loadReferences()
  },

  async loadReferences() {
    if (this.data.loading) return
    this.setData({ loading: true })
    const api = app.getApi && app.getApi()
    const orderTask = api && api.orders && api.orders.list
      ? api.orders.list().then(result => {
          const orders = listOf(result)
          if (!orders) throw new Error('订单列表响应格式无效')
          const active = orders.filter(item => TERMINAL_STATUSES.indexOf(String(item && item.status || '').toLowerCase()) < 0)
          this.setData({
            activeOrderCount: active.length,
            activeOrderText: active.length ? active.length + ' 个非终态订单' : '未发现非终态订单',
            ordersChecked: true
          })
        }).catch(error => {
          console.error('[账号注销] 查询订单参考信息失败', error)
          this.setData({ activeOrderCount: null, activeOrderText: '查询失败', ordersChecked: false })
        })
      : Promise.resolve(this.setData({ activeOrderText: '接口不可用', ordersChecked: false }))

    const walletTask = api && api.wallet && api.wallet.detail
      ? api.wallet.detail().then(result => {
          const balance = Number(result && result.balance)
          if (!Number.isFinite(balance)) throw new Error('钱包响应缺少余额')
          this.setData({ balanceText: money(balance), walletChecked: true })
        }).catch(error => {
          console.error('[账号注销] 查询钱包参考信息失败', error)
          this.setData({ balanceText: '查询失败', walletChecked: false })
        })
      : Promise.resolve(this.setData({ balanceText: '接口不可用', walletChecked: false }))

    await Promise.all([orderTask, walletTask])
    this.setData({ loading: false })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/package-client/pages/client-privacy/index' }) })
  },

  onUnavailable() {
    wx.showToast({ title: '账号注销与资格校验接口尚未开放', icon: 'none' })
  }
}))

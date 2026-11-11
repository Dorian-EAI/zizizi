const { createBusinessPage } = require('../../utils/design-business-page')
const { money, dateTime } = require('../../utils/client-finance')

const DESIGN_META = Object.freeze({
  pageId: 'page-client-payment-result',
  route: 'pages/client-payment-result/index',
  source: 'pages/client-payment-result.html',
  sourceHash: 'fnv1a-03f3aafc',
  title: '支付结果'
})

function delay(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds))
}

Page(createBusinessPage(DESIGN_META, {
  data: {
    paymentNo: '', scene: '', orderId: '', checking: false, state: 'unknown',
    kicker: 'PAYMENT STATUS UNKNOWN', iconText: '？', titleText: '支付结果待确认',
    description: '缺少可查询的支付单号，当前不会显示为支付成功。',
    statusText: '待确认', statusTone: 'warning', amountText: '—', paidAtText: '待确认'
  },

  onLoad(options) {
    const paymentNo = String(options && options.paymentNo || '').trim()
    this.setData({
      paymentNo,
      scene: String(options && options.scene || ''),
      orderId: String(options && options.orderId || '')
    })
    if (paymentNo) this.refreshStatus(true)
  },

  onUnload() {
    this._stopped = true
  },

  async refreshStatus(poll) {
    if (!this.data.paymentNo || this.data.checking) return
    this.setData({
      checking: true, kicker: 'VERIFYING PAYMENT', iconText: '…', titleText: '正在确认支付结果',
      description: '正在查询服务端支付单，请勿重复支付。', statusText: '查询中', statusTone: 'warning'
    })
    try {
      const attempts = poll ? 6 : 1
      let result = null
      for (let index = 0; index < attempts && !this._stopped; index += 1) {
        result = await getApp().getApi().wxpay.paymentStatus(this.data.paymentNo)
        const status = String(result && result.status || '').toLowerCase()
        if (status === 'paid') {
          this.applyPaid(result)
          return
        }
        if (['failed', 'closed', 'cancelled'].includes(status)) {
          this.setData({
            state: status, kicker: 'PAYMENT NOT COMPLETED', iconText: '×', titleText: '支付未完成',
            description: '服务端支付单未完成扣款，可返回后重新发起。', statusText: '未完成', statusTone: 'danger',
            amountText: money(result && result.amount), paidAtText: '未支付'
          })
          return
        }
        if (index < attempts - 1) await delay(1500)
      }
      this.setData({
        state: 'pending', kicker: 'PAYMENT PENDING', iconText: '审', titleText: '支付结果待确认',
        description: '服务端尚未确认到账，请稍后刷新；当前不会标记为成功。',
        statusText: '处理中', statusTone: 'warning', amountText: money(result && result.amount), paidAtText: '待确认'
      })
    } catch (error) {
      this.setData({
        state: 'unknown', kicker: 'PAYMENT STATUS UNKNOWN', iconText: '？', titleText: '暂时无法确认',
        description: error.message || '支付单查询失败，请勿重复支付。', statusText: '状态未知', statusTone: 'warning'
      })
    } finally {
      if (!this._stopped) this.setData({ checking: false })
    }
  },

  applyPaid(result) {
    this.setData({
      state: 'paid', kicker: 'PAYMENT CONFIRMED', iconText: '✓', titleText: '支付成功',
      description: this.data.scene === 'recharge' ? '充值款项已由服务端确认到账。' : '订单款项已由服务端确认到账。',
      statusText: '支付完成', statusTone: 'success', amountText: money(result.amount),
      paidAtText: dateTime(result.paid_at)
    })
  },

  onRefresh() {
    this.refreshStatus(false)
  },

  onViewContext() {
    if (this.data.scene === 'recharge') {
      wx.redirectTo({ url: '/package-client/pages/client-wallet/index' })
      return
    }
    if (this.data.orderId) {
      wx.redirectTo({ url: '/pages/order-detail-client/index?id=' + encodeURIComponent(this.data.orderId) })
      return
    }
    wx.redirectTo({ url: '/pages/client-orders/index' })
  }
}))

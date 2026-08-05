const { createBusinessPage } = require('../../utils/design-business-page')
const { money } = require('../../utils/client-finance')
const { requestPayment, isPaymentCancelled } = require('../../utils/wx-payment')
const idempotency = require('../../utils/idempotency')

const PENDING_STORAGE_KEY = '__CLIENT_WALLET_RECHARGE_PENDING__'
const DESIGN_META = Object.freeze({
  pageId: 'page-client-wallet-recharge',
  route: 'pages/client-wallet-recharge/index',
  source: 'pages/client-wallet-recharge.html',
  sourceHash: 'fnv1a-2b07fd02',
  title: '钱包充值'
})

function delay(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds))
}

Page(createBusinessPage(DESIGN_META, {
  data: {
    balanceText: '—', selectedAmount: 500, customAmount: '', submitting: false,
    checking: false, paymentNo: '', paymentStatus: '', statusText: '待确认金额',
    statusTone: 'warning'
  },

  onLoad() {
    try {
      const pending = wx.getStorageSync(PENDING_STORAGE_KEY)
      if (pending && pending.paymentNo) {
        this._pendingSlot = pending.slot || ''
        this.setData({
          paymentNo: pending.paymentNo,
          selectedAmount: Number(pending.amount) || 500,
          paymentStatus: 'pending', statusText: '上笔充值待确认', statusTone: 'warning'
        })
      }
    } catch (error) {
      console.warn('[钱包充值] 恢复待确认支付单失败', error)
    }
  },

  onShow() {
    this.loadBalance()
    if (this.data.paymentNo && !this.data.checking) this.queryPayment(false)
  },

  async loadBalance() {
    try {
      const wallet = await getApp().getApi().wallet.detail()
      this.setData({ balanceText: money(wallet && wallet.balance) })
    } catch (error) {
      this.setData({ balanceText: '—' })
    }
  },

  onSelectAmount(event) {
    if (this.data.paymentNo) {
      wx.showToast({ title: '请先确认上笔充值结果', icon: 'none' })
      return
    }
    const amount = Number(event.currentTarget.dataset.amount)
    if (!Number.isFinite(amount)) return
    this.setData({ selectedAmount: amount, customAmount: '', statusText: '金额已确认', statusTone: 'success' })
  },

  onCustomAmount(event) {
    if (this.data.paymentNo) return
    const raw = String(event.detail.value || '').replace(/[^0-9.]/g, '')
    const amount = Number(raw)
    const valid = amount >= 1 && amount <= 5000
    this.setData({
      customAmount: raw,
      selectedAmount: Number.isFinite(amount) ? amount : 0,
      statusText: valid ? '金额已确认' : '请输入 1–5,000 元',
      statusTone: valid ? 'success' : 'warning'
    })
  },

  async onSubmit() {
    if (this.data.submitting || this.data.checking) return
    if (this.data.paymentNo) {
      await this.queryPayment(true)
      return
    }
    const amount = Number(this.data.selectedAmount)
    if (!Number.isFinite(amount) || amount < 1 || amount > 5000 || Math.round(amount * 100) !== amount * 100) {
      wx.showToast({ title: '请输入 1–5,000 元且最多两位小数', icon: 'none' })
      return
    }

    const slot = 'client-wallet-recharge:' + Math.round(amount * 100)
    const key = idempotency.getOrCreate(slot)
    this.setData({ submitting: true, statusText: '正在创建支付单', statusTone: 'warning' })
    try {
      const params = await getApp().getApi().wxpay.rechargeJsapi(amount, key)
      const paymentNo = params && params.payment_no
      if (!paymentNo) throw new Error('服务端未返回支付单号')
      this._pendingSlot = slot
      this.setData({ paymentNo, paymentStatus: 'pending', statusText: '等待微信支付', statusTone: 'warning' })
      wx.setStorageSync(PENDING_STORAGE_KEY, { paymentNo, amount, slot })
      try {
        await requestPayment(params)
      } catch (error) {
        if (!isPaymentCancelled(error)) throw error
      }
      await this.queryPayment(true)
    } catch (error) {
      this.setData({ statusText: error.message || '充值请求失败', statusTone: 'danger' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  async queryPayment(poll) {
    const paymentNo = this.data.paymentNo
    if (!paymentNo || this.data.checking) return
    this.setData({ checking: true, statusText: '正在向服务端确认', statusTone: 'warning' })
    try {
      const attempts = poll ? 6 : 1
      let result = null
      for (let index = 0; index < attempts; index += 1) {
        result = await getApp().getApi().wxpay.paymentStatus(paymentNo)
        const status = String(result && result.status || '').toLowerCase()
        if (status === 'paid') {
          this.completePayment()
          return
        }
        if (['failed', 'closed', 'cancelled'].includes(status)) {
          this.clearPending()
          this.setData({ paymentStatus: status, statusText: '支付未完成，可重新发起', statusTone: 'danger' })
          return
        }
        if (index < attempts - 1) await delay(1500)
      }
      this.setData({
        paymentStatus: String(result && result.status || 'pending'),
        statusText: '支付结果待确认，请稍后刷新', statusTone: 'warning'
      })
    } catch (error) {
      this.setData({ statusText: '暂未查到最终结果，请勿重复充值', statusTone: 'warning' })
    } finally {
      this.setData({ checking: false })
    }
  },

  completePayment() {
    const paymentNo = this.data.paymentNo
    this.clearPending()
    this.setData({ paymentStatus: 'paid', statusText: '服务端已确认到账', statusTone: 'success' })
    this.loadBalance()
    wx.navigateTo({ url: '/pages/client-payment-result/index?paymentNo=' + encodeURIComponent(paymentNo) + '&scene=recharge' })
  },

  clearPending() {
    if (this._pendingSlot) idempotency.clear(this._pendingSlot)
    this._pendingSlot = ''
    try { wx.removeStorageSync(PENDING_STORAGE_KEY) } catch (error) {}
    this.setData({ paymentNo: '' })
  }
}))

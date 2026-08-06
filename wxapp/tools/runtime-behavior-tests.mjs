import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(import.meta.url)
let pageDefinition = null
let paymentStatus = 'pending'
let orderReloads = 0
const orderJsapiCalls = []
const rechargeJsapiCalls = []
const toastTitles = []
const navigatedUrls = []
const storage = new Map()

const latestOrder = {
  order_no: 'ORDER-17',
  final_price: 88,
  allowed_actions: ['confirm_and_pay']
}
const latestQuote = {
  order_id: 17,
  order_no: 'ORDER-17',
  order_version: 3,
  original_amount: 88,
  discount_amount: 0,
  payable_amount: 88,
  coupon_id: null,
  payment_methods: [{ key: 'wechat', enabled: true, disabled_reason: '' }],
  active_payment: null,
  expires_at: '2026-08-03T22:00:00Z'
}

const api = {
  orders: {
    detail: async () => latestOrder,
    paymentQuote: async () => latestQuote
  },
  wxpay: {
    orderJsapi: async (...args) => {
      orderJsapiCalls.push(args)
      return {
        timeStamp: '1785750000',
        nonceStr: 'nonce',
        package: 'prepay_id=test',
        signType: 'RSA',
        paySign: 'signed',
        payment_no: 'PAY-17',
        pay_amount: latestQuote.payable_amount,
        discount_amount: latestQuote.discount_amount,
        order_version: latestQuote.order_version
      }
    },
    rechargeJsapi: async (...args) => {
      rechargeJsapiCalls.push(args)
      return {
        timeStamp: '1785750000',
        nonceStr: 'recharge-nonce',
        package: 'prepay_id=recharge',
        signType: 'RSA',
        paySign: 'recharge-signed',
        payment_no: 'PAY-RECHARGE'
      }
    },
    paymentStatus: async () => ({ status: paymentStatus, amount: 500, paid_at: paymentStatus === 'paid' ? '2026-08-03T22:00:00Z' : null })
  },
  wallet: {
    pay: async () => ({ status: 'pending' }),
    detail: async () => ({ balance: 500 })
  }
}

globalThis.getApp = () => ({
  globalData: { useMock: false, statusBarHeight: 20 },
  getApi: () => api
})
globalThis.Page = definition => { pageDefinition = definition }
globalThis.wx = {
  showLoading() {},
  hideLoading() {},
  showToast(options) { toastTitles.push(options && options.title) },
  requestPayment(options) { options.success({}) },
  getStorageSync(key) { return storage.get(key) },
  setStorageSync(key, value) { storage.set(key, value) },
  removeStorageSync(key) { storage.delete(key) },
  navigateTo(options) { navigatedUrls.push(options && options.url) },
  navigateBack() {}
}

require(join(root, 'pages', 'client-payment', 'index.js'))
assert.ok(pageDefinition, '确认支付页必须注册 Page')

function createPage(data) {
  const page = Object.assign({}, pageDefinition)
  page.data = Object.assign({}, pageDefinition.data, data || {})
  page.setData = patch => Object.assign(page.data, patch)
  page.loadOrder = async () => { orderReloads += 1 }
  return page
}

const page = createPage({
  orderId: '17',
  order: latestOrder,
  quote: latestQuote,
  loading: false,
  paying: false,
  canPay: true,
  selectedMethod: 'wechat',
  paymentMethods: [{ key: 'wechat', enabled: true }],
  selectedCoupon: null
})
page.schedulePaymentPoll = () => {}

const firstKey = page.getPaymentAttemptKey()
assert.equal(page.getPaymentAttemptKey(), firstKey, '同一次支付尝试必须复用同一幂等键')
assert.ok(firstKey.length >= 8 && firstKey.length <= 128, '幂等键长度必须为 8–128')

paymentStatus = 'pending'
toastTitles.length = 0
await page.onPay()
assert.equal(orderJsapiCalls.length, 1, '微信支付只应创建一次服务端预支付请求')
assert.equal(orderJsapiCalls[0][2], firstKey, '创建预支付必须把当前幂等键传给 API')
assert.equal(orderJsapiCalls[0][3], latestQuote.order_version, '创建预支付必须传服务端报价对应的订单版本')
assert.equal(toastTitles.includes('支付成功'), false, '微信客户端回调后、服务端 pending 时不得提示成功')
assert.equal(page.data.pendingPaymentNo, 'PAY-17')

paymentStatus = 'success'
toastTitles.length = 0
await page.checkPaymentResult()
assert.equal(toastTitles.includes('支付成功'), false, '非规范 success 状态不得被客户端当作服务端 paid')
assert.equal(page.data.pendingPaymentNo, 'PAY-17')

paymentStatus = 'paid'
toastTitles.length = 0
orderReloads = 0
await page.checkPaymentResult()
assert.equal(toastTitles.includes('支付成功'), true, '只有服务端 paid 才能提示支付成功')
assert.equal(page.data.pendingPaymentNo, '')
assert.equal(orderReloads, 1, '服务端确认 paid 后必须刷新订单')

pageDefinition = null
require(join(root, 'pages', 'client-wallet-recharge', 'index.js'))
assert.ok(pageDefinition, '钱包充值页必须注册 Page')

const rechargePage = createPage({
  balanceText: '0.00',
  selectedAmount: 500,
  customAmount: '',
  submitting: false,
  checking: false,
  paymentNo: '',
  paymentStatus: '',
  statusText: '金额已确认',
  statusTone: 'success'
})
rechargePage.loadBalance = async () => {}

paymentStatus = 'success'
navigatedUrls.length = 0
rechargePage.setData({ paymentNo: 'PAY-PENDING' })
await rechargePage.queryPayment(false)
assert.equal(navigatedUrls.length, 0, '充值支付单的非规范 success 状态不得进入成功结果页')
assert.equal(rechargePage.data.paymentNo, 'PAY-PENDING', '充值结果未知时必须保留原支付单供重查')

paymentStatus = 'paid'
rechargeJsapiCalls.length = 0
navigatedUrls.length = 0
rechargePage.setData({ paymentNo: '', checking: false })
await rechargePage.onSubmit()
assert.equal(rechargeJsapiCalls.length, 1, '一次充值操作只应创建一次 JSAPI 预支付请求')
assert.ok(String(rechargeJsapiCalls[0][1] || '').length >= 8, '充值必须向 API 传有效幂等键')
assert.equal(navigatedUrls.some(url => /client-payment-result\/index\?paymentNo=PAY-RECHARGE/.test(url)), true, '服务端 paid 后才能进入充值成功结果页')
assert.equal(rechargePage.data.paymentNo, '', '服务端 paid 后应清理待确认支付单')

console.log('运行行为检查通过')
console.log('- 订单支付幂等与服务端最终态：4/4')
console.log('- 钱包充值幂等与服务端最终态：5/5')

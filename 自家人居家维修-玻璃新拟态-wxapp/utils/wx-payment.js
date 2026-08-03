// 微信支付统一入口：校验后端签名参数，避免缺少参数时被误判为支付成功。
function createPaymentError(message, code) {
  const error = new Error(message)
  error.code = code
  return error
}

function isPaymentCancelled(error) {
  const message = String((error && (error.errMsg || error.message)) || '')
  return message.toLowerCase().indexOf('cancel') >= 0
}

function requestPayment(params) {
  const app = getApp()
  if (app && app.globalData && app.globalData.useMock) {
    return Promise.resolve({ mock: true })
  }

  const required = ['timeStamp', 'nonceStr', 'package', 'paySign']
  const missing = required.filter(key => !params || !params[key])
  if (missing.length) {
    return Promise.reject(createPaymentError(
      '支付参数不完整：' + missing.join(', '),
      'INVALID_PAYMENT_PARAMS'
    ))
  }

  return new Promise((resolve, reject) => {
    wx.requestPayment({
      timeStamp: String(params.timeStamp),
      nonceStr: params.nonceStr,
      package: params.package,
      signType: params.signType || 'RSA',
      paySign: params.paySign,
      success: resolve,
      fail: reject
    })
  })
}

module.exports = { requestPayment, isPaymentCancelled }

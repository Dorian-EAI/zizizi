const app = getApp()

const BASE_URL = app.globalData.baseURL || 'http://localhost:8000'

function request(options) {
  return new Promise((resolve, reject) => {
    const token = app.globalData.token
    wx.request({
      url: `${BASE_URL}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...(options.header || {})
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          const body = res.data
          if (body.code === 0 || body.code === 200) {
            resolve(body.data)
          } else {
            wx.showToast({ title: body.message || '请求失败', icon: 'none' })
            reject(body)
          }
        } else {
          wx.showToast({ title: `HTTP ${res.statusCode}`, icon: 'none' })
          reject(res)
        }
      },
      fail(err) {
        wx.showToast({ title: '网络错误', icon: 'none' })
        reject(err)
      }
    })
  })
}

module.exports = {
  get: (url, data) => request({ url, method: 'GET', data }),
  post: (url, data) => request({ url, method: 'POST', data }),
  put: (url, data) => request({ url, method: 'PUT', data }),
  del: (url, data) => request({ url, method: 'DELETE', data })
}

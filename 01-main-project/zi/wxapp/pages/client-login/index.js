const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    agreed: false,
    loggingIn: false,
    icons: {}
  },

  onLoad() {
    this.setData({
      icons: {
        home: buildIcon('home', COLORS.white),
        phone: buildIcon('phone', COLORS.white),
        arrow: buildIcon('chevronRight', COLORS.text3),
        check: buildIcon('check', COLORS.white)
      }
    })
    if (app.globalData.token && app.globalData.role === 'client') {
      wx.redirectTo({ url: '/pages/client-home/index' })
    }
  },

  onToggleAgreement() {
    this.setData({ agreed: !this.data.agreed })
  },

  async onAgreementTap(e) {
    const key = e.currentTarget.dataset.key
    const document = key === 'privacy' ? 'privacy-policy' : 'user-agreement'
    wx.navigateTo({ url: '/package-client/pages/client-agreement/index?document=' + document })
  },

  getWxLoginCode() {
    if (app.globalData.useMock) return Promise.resolve('mock-login-code')
    return new Promise((resolve, reject) => {
      wx.login({
        timeout: 10000,
        success: result => result && result.code ? resolve(result.code) : reject(new Error('未获取到微信登录凭证')),
        fail: reject
      })
    })
  },

  async onWechatLogin() {
    if (!this.data.agreed) {
      wx.showToast({ title: '请先阅读并同意协议', icon: 'none' })
      return
    }
    if (this.data.loggingIn) return
    this.setData({ loggingIn: true })
    wx.showLoading({ title: '登录中', mask: true })
    try {
      const api = app.getApi()
      const code = await this.getWxLoginCode()
      const result = await api.auth.wxLogin(code)
      if (!result || !result.token) throw new Error('登录响应缺少 Token')
      app.saveLogin(result.token, null, 'client')
      let userInfo = null
      try {
        userInfo = await api.auth.me()
      } catch (error) {
        if (error && error.code === 'AUTH_REQUIRED') throw error
        console.warn('账号资料暂时不可用', error)
      }
      app.saveLogin(result.token, userInfo, 'client')
      app.setRole('client')
      wx.hideLoading()
      wx.redirectTo({ url: '/pages/client-home/index' })
    } catch (error) {
      wx.hideLoading()
      console.error('微信登录失败', error)
      wx.showToast({ title: (error && error.message) || '登录失败，请重试', icon: 'none' })
    } finally {
      this.setData({ loggingIn: false })
    }
  },

  onPhoneLogin() {
    wx.showToast({ title: '暂未开放手机号独立登录', icon: 'none' })
  }
})

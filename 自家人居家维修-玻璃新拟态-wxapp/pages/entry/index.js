// pages/entry/index.js — 角色选择入口页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    clientIcon: '',
    workerIcon: '',
    loggingIn: false
  },

  onLoad(query) {
    // 允许 401 重定向完成；成功登录时 saveLogin 会再次复位该标记。
    if (query && query.reason) app.globalData._authRedirecting = false
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      clientIcon: buildIcon('user', COLORS.brand),
      workerIcon: buildIcon('hall', COLORS.brandWorker)
    })
    // 只有存在登录态时才自动进入首页，避免入口页与 401 重定向互相循环。
    const role = app.globalData.role
    if (role && (app.globalData.token || app.globalData.useMock)) {
      this.goRole(role)
    }
  },

  onClient() {
    if (app.globalData.token && app.globalData.role === 'client') {
      this.goRole('client')
      return
    }
    wx.navigateTo({ url: '/pages/client-login/index' })
  },
  onWorker() { this.loginAndEnter('worker') },

  getWxLoginCode() {
    if (app.globalData.useMock) return Promise.resolve('mock-login-code')
    return new Promise((resolve, reject) => {
      wx.login({
        timeout: 10000,
        success: result => {
          if (result && result.code) resolve(result.code)
          else reject(new Error('未获取到微信登录凭证'))
        },
        fail: reject
      })
    })
  },

  async loginAndEnter(role) {
    if (this.data.loggingIn) return
    if (app.globalData.token && app.globalData.role === role) {
      this.goRole(role)
      return
    }

    this.setData({ loggingIn: true })
    wx.showLoading({ title: '登录中', mask: true })
    try {
      const api = app.getApi()
      const code = await this.getWxLoginCode()
      const result = role === 'worker'
        ? await api.auth.workerLogin(code)
        : await api.auth.wxLogin(code)
      if (!result || !result.token) throw new Error('登录响应缺少 Token')

      // 先保存 Token，再请求账号资料；资料失败不阻断有效登录。
      app.saveLogin(result.token, null, role)
      let userInfo = null
      try {
        userInfo = role === 'worker' ? await api.auth.workerMe() : await api.auth.me()
      } catch (error) {
        console.warn('登录成功，但账号资料暂时不可用', error)
      }
      app.saveLogin(result.token, userInfo, role)
      wx.hideLoading()
      this.goRole(role)
    } catch (error) {
      wx.hideLoading()
      console.error('微信登录失败', error)
      wx.showToast({ title: (error && error.message) || '登录失败，请重试', icon: 'none' })
    } finally {
      this.setData({ loggingIn: false })
    }
  },

  goRole(role) {
    app.setRole(role)
    const path = role === 'worker' ? '/pages/worker-home/index' : '/pages/client-home/index'
    wx.redirectTo({ url: path })
  }
})

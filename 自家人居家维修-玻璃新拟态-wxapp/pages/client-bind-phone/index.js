const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

function maskPhone(value) {
  const phone = String(value || '').replace(/\s+/g, '')
  if (/^1\d{10}$/.test(phone)) return phone.slice(0, 3) + '****' + phone.slice(-4)
  return phone || '尚未绑定'
}

function validPhone(value) {
  return /^1[3-9]\d{9}$/.test(String(value || '').trim())
}

const designPage = createDesignPage({
  pageId: 'page-client-bind-phone',
  route: 'pages/client-bind-phone/index',
  source: 'pages/client-bind-phone.html',
  sourceHash: 'fnv1a-fa6331e8',
  title: '绑定手机'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    currentPhone: '正在读取',
    newPhone: '',
    newCode: '',
    countdown: 0,
    sending: false,
    binding: false
  }),

  onLoad() {
    this.loadCurrentPhone()
  },

  onUnload() {
    this.clearCountdown()
  },

  async loadCurrentPhone() {
    try {
      const user = await app.getApi().auth.me()
      this.setData({ currentPhone: maskPhone(user && user.phone) })
    } catch (error) {
      console.error('[绑定手机] 读取当前手机号失败', error)
      this.setData({ currentPhone: '暂时无法读取' })
    }
  },

  onPhoneInput(event) {
    this.setData({ newPhone: String(event.detail.value || '').replace(/\D/g, '').slice(0, 11) })
  },

  onCodeInput(event) {
    this.setData({ newCode: String(event.detail.value || '').replace(/\D/g, '').slice(0, 8) })
  },

  async onSendNewCode() {
    if (this.data.sending || this.data.countdown > 0) return
    if (!validPhone(this.data.newPhone)) {
      wx.showToast({ title: '请输入有效的 11 位手机号', icon: 'none' })
      return
    }
    this.setData({ sending: true })
    try {
      const result = await app.getApi().sms.sendCode(this.data.newPhone, 'bind_phone')
      if (!result || result.sent !== true) throw new Error('短信服务未确认发送成功')
      wx.showToast({ title: '验证码已发送', icon: 'success' })
      this.startCountdown(60)
    } catch (error) {
      console.error('[绑定手机] 发送验证码失败', error)
      if (error && error.message === '短信服务未确认发送成功') {
        wx.showToast({ title: error.message, icon: 'none' })
      }
    } finally {
      this.setData({ sending: false })
    }
  },

  startCountdown(seconds) {
    this.clearCountdown()
    this.setData({ countdown: seconds })
    this._countdownTimer = setInterval(() => {
      const next = this.data.countdown - 1
      if (next <= 0) {
        this.clearCountdown()
        this.setData({ countdown: 0 })
      } else {
        this.setData({ countdown: next })
      }
    }, 1000)
  },

  clearCountdown() {
    if (this._countdownTimer) clearInterval(this._countdownTimer)
    this._countdownTimer = null
  },

  async onBindPhone() {
    if (this.data.binding) return
    if (!validPhone(this.data.newPhone)) {
      wx.showToast({ title: '请输入有效的 11 位手机号', icon: 'none' })
      return
    }
    if (!/^\d{4,8}$/.test(this.data.newCode)) {
      wx.showToast({ title: '请输入短信验证码', icon: 'none' })
      return
    }
    this.setData({ binding: true })
    try {
      const api = app.getApi()
      await api.auth.bindPhone(this.data.newPhone, this.data.newCode)
      const user = await api.auth.me()
      if (!user || String(user.phone || '') !== this.data.newPhone) {
        throw new Error('服务端未返回已绑定的新手机号')
      }
      if (app.saveLogin) app.saveLogin(app.globalData.token, user, app.globalData.role || 'client')
      else {
        app.globalData.userInfo = user
        try { wx.setStorageSync('userInfo', user) } catch (error) {}
      }
      wx.showToast({ title: '手机号已绑定', icon: 'success' })
      setTimeout(() => {
        wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-account-security/index' }) })
      }, 500)
    } catch (error) {
      console.error('[绑定手机] 绑定失败', error)
      if (error && error.message === '服务端未返回已绑定的新手机号') {
        wx.showToast({ title: error.message, icon: 'none' })
      }
    } finally {
      this.setData({ binding: false })
    }
  },

  onOldPhoneUnavailable() {
    wx.showToast({ title: '后端当前未提供原手机号验证码契约', icon: 'none' })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-account-security/index' }) })
  }
}))

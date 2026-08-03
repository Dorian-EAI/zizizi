const api = require('../../../utils/request')

Page({
  data: {
    workerInfo: {
      name: '张师傅',
      completed_orders: 328,
      rating: 98
    },
    settings: {
      receive_range: 5,
      service_categories: '防水/家电/管道',
      receive_enabled: true,
      auto_receive: false,
      notify_new_order: true,
      notify_system: true,
      notify_income: true
    }
  },

  onLoad() {
    this.loadWorkerInfo()
    this.loadSettings()
  },

  loadWorkerInfo() {
    api.get('/api/worker/profile').then(data => {
      if (data) {
        this.setData({ workerInfo: data })
      }
    }).catch(() => {})
  },

  loadSettings() {
    api.get('/api/worker/settings').then(data => {
      if (data) {
        this.setData({ settings: Object.assign({}, this.data.settings, data) })
      }
    }).catch(() => {})
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onReceiveRange() {
    wx.showToast({ title: '设置接单范围', icon: 'none' })
  },

  onServiceCategory() {
    wx.showToast({ title: '设置服务分类', icon: 'none' })
  },

  onToggleReceive() {
    const enabled = !this.data.settings.receive_enabled
    this.setData({ 'settings.receive_enabled': enabled })
    api.put('/api/worker/settings', { receive_enabled: enabled }).catch(() => {})
  },

  onToggleAutoReceive() {
    const enabled = !this.data.settings.auto_receive
    this.setData({ 'settings.auto_receive': enabled })
    api.put('/api/worker/settings', { auto_receive: enabled }).catch(() => {})
  },

  onChangePassword() {
    wx.showToast({ title: '修改密码', icon: 'none' })
  },

  onBindPhone() {
    wx.showToast({ title: '绑定手机', icon: 'none' })
  },

  onRealname() {
    wx.showToast({ title: '实名认证', icon: 'none' })
  },

  onCertificates() {
    wx.showToast({ title: '资质证书', icon: 'none' })
  },

  onToggleNewOrderNotify() {
    const val = !this.data.settings.notify_new_order
    this.setData({ 'settings.notify_new_order': val })
  },

  onToggleSystemNotify() {
    const val = !this.data.settings.notify_system
    this.setData({ 'settings.notify_system': val })
  },

  onToggleIncomeNotify() {
    const val = !this.data.settings.notify_income
    this.setData({ 'settings.notify_income': val })
  },

  onClearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '确定要清除本地缓存吗？',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({ title: '缓存已清除', icon: 'success' })
        }
      }
    })
  },

  onAbout() {
    wx.showToast({ title: '关于我们', icon: 'none' })
  },

  onUserAgreement() {
    wx.showToast({ title: '用户协议', icon: 'none' })
  },

  onPrivacyPolicy() {
    wx.showToast({ title: '隐私政策', icon: 'none' })
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          const app = getApp()
          if (app && app.globalData) {
            app.globalData.token = null
            app.globalData.userInfo = null
          }
          wx.removeStorageSync('token')
          wx.removeStorageSync('userInfo')
          wx.reLaunch({ url: '/pages/index/index' })
        }
      }
    })
  }
})

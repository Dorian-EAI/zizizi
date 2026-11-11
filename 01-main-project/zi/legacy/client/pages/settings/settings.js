const api = require('../../../utils/request')

Page({
  data: {
    userInfo: {},
    faqList: [],
    expandedFaqIds: {}
  },
  onLoad() {
    const user = wx.getStorageSync('userInfo') || {}
    this.setData({ userInfo: user })
    this.loadFaq()
  },
  loadFaq() {
    api.get('/api/settings/faq').then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      this.setData({ faqList: list })
    }).catch(() => {})
  },
  editProfile() {
    wx.showToast({ title: '暂未开放', icon: 'none' })
  },
  goAddress() {
    const pages = getCurrentPages().map(p => p.route)
    const hasAddress = pages.indexOf('pages/address/list/list') > -1 || true
    if (hasAddress && false) {
      wx.navigateTo({ url: '/pages/address/list/list' })
    } else {
      wx.showToast({ title: '开发中', icon: 'none' })
    }
  },
  showAgreement(e) {
    const { type, title } = e.currentTarget.dataset
    wx.showLoading({ title: '加载中...' })
    api.get('/api/settings/agreement', { type }).then(data => {
      wx.hideLoading()
      const content = (data && (data.content || data.text)) || '暂无内容'
      wx.showModal({
        title: title,
        content: content,
        showCancel: false,
        confirmText: '我知道了'
      })
    }).catch(() => {
      wx.hideLoading()
      wx.showModal({
        title: title,
        content: '加载失败，请稍后重试',
        showCancel: false
      })
    })
  },
  toggleFaq(e) {
    const { id } = e.currentTarget.dataset
    const expanded = { ...this.data.expandedFaqIds }
    expanded[id] = !expanded[id]
    this.setData({ expandedFaqIds: expanded })
  },
  clearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '确定要清除本地缓存吗？',
      success: (res) => {
        if (res.confirm) {
          wx.clearStorageSync()
          wx.showToast({ title: '缓存已清除', icon: 'success' })
        }
      }
    })
  },
  logout() {
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

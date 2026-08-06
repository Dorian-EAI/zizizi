const api = require('../../utils/request')

Page({
  data: {
    user: null,
    wallet: null,
    unreadCount: 0
  },
  onShow() {
    this.loadUser()
    this.loadWallet()
    this.loadMessages()
  },
  loadUser() {
    const user = wx.getStorageSync('userInfo')
    if (user) this.setData({ user })
  },
  loadWallet() {
    api.get('/api/wallet').then(data => {
      this.setData({ wallet: data })
    }).catch(() => {})
  },
  loadMessages() {
    api.get('/api/messages', { page: 1, size: 1 }).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      const unread = (data.unread_count != null) ? data.unread_count : list.filter(m => !m.is_read).length
      this.setData({ unreadCount: unread })
    }).catch(() => {})
  },
  onEditProfile() {
    wx.showToast({ title: '编辑资料', icon: 'none' })
  },
  goHome() {
    wx.switchTab({ url: '/pages/index/index' })
  },
  goPublish() {
    wx.switchTab({ url: '/pages/publish/publish' })
  },
  goOrders() {
    wx.switchTab({ url: '/pages/orders/orders' })
  },
  goReviews() {
    wx.navigateTo({ url: '/pages/review/mine/mine' })
  },
  goFavorites() {
    wx.showToast({ title: '功能开发中', icon: 'none' })
  },
  goAddress() {
    wx.showToast({ title: '地址管理', icon: 'none' })
  },
  goCoupons() {
    wx.navigateTo({ url: '/pages/coupon/list/list' })
  },
  goWallet() {
    wx.navigateTo({ url: '/pages/wallet/wallet' })
  },
  goInvoice() {
    wx.showToast({ title: '发票与报销', icon: 'none' })
  },
  goNotifications() {
    wx.showToast({ title: '消息通知', icon: 'none' })
  },
  goSecurity() {
    wx.showToast({ title: '账号安全', icon: 'none' })
  },
  goPrivacy() {
    wx.showToast({ title: '隐私设置', icon: 'none' })
  },
  goService() {
    wx.navigateTo({ url: '/pages/service/list/list' })
  },
  goSettings() {
    wx.navigateTo({ url: '/pages/settings/settings' })
  },
  goAbout() {
    wx.showToast({ title: '关于我们 v2.4.0', icon: 'none' })
  }
})

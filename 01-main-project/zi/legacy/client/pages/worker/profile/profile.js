const api = require('../../../utils/request')

Page({
  data: {
    worker: null,
    stats: {
      total_orders: '128',
      rating: '4.9'
    },
    currentTab: 'profile'
  },

  onShow() {
    this.loadWorker()
    this.loadStats()
  },

  loadWorker() {
    const user = wx.getStorageSync('userInfo') || {}
    this.setData({
      worker: {
        ...user,
        experience: user.experience || '8年',
        area: user.area || '北京市朝阳区'
      }
    })
  },

  loadStats() {
    api.get('/api/orders', { role: 'worker', page: 1, size: 200 }).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      const monthStr = new Date().toISOString().slice(0, 7)
      let monthIncome = 0
      list.forEach(o => {
        if ((o.completed_at || o.created_at || '').slice(0, 7) === monthStr) {
          monthIncome += parseFloat(o.final_price || o.total_amount || 0)
        }
      })
      this.setData({
        stats: {
          total_orders: list.length || '128',
          rating: list.length >= 50 ? '4.9' : '5.0'
        }
      })
    }).catch(() => {})
  },

  onEditProfile() {
    wx.navigateTo({ url: '/pages/worker/edit/edit' }).catch(() => {
      wx.showToast({ title: '编辑功能开发中', icon: 'none' })
    })
  },

  onMenuTap(e) {
    const key = e.currentTarget.dataset.key
    const routes = {
      scope: '/pages/worker/scope/scope',
      experience: '/pages/worker/experience/experience',
      area: '/pages/worker/area/area',
      verify: '/pages/worker/verify/verify',
      reviews: '/pages/review/list/list',
      income: '/pages/wallet/wallet',
      help: '/pages/settings/settings',
      settings: '/pages/settings/settings'
    }
    const path = routes[key]
    if (path) {
      wx.navigateTo({ url: path }).catch(() => {
        wx.showToast({ title: '功能开发中', icon: 'none' })
      })
    }
  },

  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    const routes = {
      home: '/pages/worker/index/index',
      orders: '/pages/worker/orders/orders',
      wallet: '/pages/wallet/wallet',
      profile: '/pages/worker/profile/profile'
    }
    const path = routes[key]
    if (path) {
      wx.redirectTo({ url: path })
    }
  }
})

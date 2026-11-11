const api = require('../../../utils/request')

Page({
  data: {
    myCards: [],
    templates: [],
    loading: false
  },
  onLoad() {
    this.loadAll()
  },
  loadAll() {
    this.setData({ loading: true })
    Promise.all([
      api.get('/api/annual-cards/my').catch(() => ({ list: [] })),
      api.get('/api/annual-cards/templates').catch(() => ({ list: [] }))
    ]).then(([my, tpl]) => {
      const myCards = Array.isArray(my) ? my : (my.list || [])
      const templates = Array.isArray(tpl) ? tpl : (tpl.list || [])
      this.setData({ myCards, templates, loading: false })
    }).catch(() => {
      this.setData({ loading: false })
    })
  },
  onPullDownRefresh() {
    this.loadAll()
    wx.stopPullDownRefresh()
  },
  buyCard(e) {
    const { id, name } = e.currentTarget.dataset
    wx.showModal({
      title: '购买年卡',
      content: `您即将购买「${name}」，请联系客服开通。`,
      confirmText: '联系客服',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({ title: '请联系客服开通', icon: 'none', duration: 2000 })
        }
      }
    })
  }
})

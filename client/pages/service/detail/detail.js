Page({
  data: {
    service: {
      name: '防水维修',
      rating: '4.9',
      service_count: '128'
    },
    selectedPrice: 1,
    isFav: false,
    masters: [
      { id: 1, name: '王师傅', rating: '4.9', services: '326' },
      { id: 2, name: '陈师傅', rating: '4.8', services: '215' }
    ],
    reviews: [
      { id: 1, name: '李女士', date: '2026-07-15', text: '师傅很专业，防水做得很细致，施工后没有再渗水，沟通也很顺畅，强烈推荐！' },
      { id: 2, name: '张先生', date: '2026-07-09', text: '响应很快，三分钟就有师傅接单，价格透明无隐形消费，整体体验非常好。' }
    ]
  },

  onLoad(options) {
    const key = options.key || options.id || 'waterproof'
    this.setData({ serviceKey: key })
  },

  onBack() {
    wx.navigateBack()
  },

  pickPrice(e) {
    this.setData({ selectedPrice: e.currentTarget.dataset.index })
  },

  onToggleFav() {
    this.setData({ isFav: !this.data.isFav })
    wx.showToast({
      title: this.data.isFav ? '已收藏' : '取消收藏',
      icon: 'none'
    })
  },

  onService() {
    wx.navigateTo({ url: '/pages/service/list/list' })
  },

  onBookNow() {
    wx.showToast({ title: '跳转预约', icon: 'none' })
  },

  bookMaster(e) {
    wx.showToast({ title: '预约师傅 #' + e.currentTarget.dataset.id, icon: 'none' })
  },

  goAllMasters() {
    wx.showToast({ title: '查看全部师傅', icon: 'none' })
  },

  goAllReviews() {
    wx.showToast({ title: '查看全部评价', icon: 'none' })
  }
})

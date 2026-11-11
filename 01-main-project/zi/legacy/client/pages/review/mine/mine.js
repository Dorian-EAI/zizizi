const api = require('../../../utils/request')

Page({
  data: {
    reviews: [],
    statusTabs: [
      { key: '', label: '全部' },
      { key: 'pending', label: '待审核' },
      { key: 'approved', label: '已通过' },
      { key: 'rejected', label: '未通过' },
    ],
    activeStatus: '',
    page: 1,
    hasMore: true,
    loading: false
  },
  onLoad() { this.loadReviews(true) },
  onPullDownRefresh() {
    this.loadReviews(true).then(() => wx.stopPullDownRefresh())
  },
  loadReviews(reset) {
    if (this.data.loading) return Promise.resolve()
    if (!reset && !this.data.hasMore) return Promise.resolve()
    this.setData({ loading: true })
    const page = reset ? 1 : this.data.page
    const params = { page, size: 10 }
    if (this.data.activeStatus) params.status = this.data.activeStatus
    return api.get('/api/reviews/mine', params).then(data => {
      const list = data.list || []
      this.setData({
        reviews: reset ? list : this.data.reviews.concat(list),
        page: page + 1,
        hasMore: list.length === 10,
        loading: false
      })
    }).catch(() => this.setData({ loading: false }))
  },
  switchStatus(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ activeStatus: key, reviews: [], page: 1, hasMore: true }, () => {
      this.loadReviews(true)
    })
  },
  onReachBottom() { this.loadReviews() },
  previewImage(e) {
    const { url, urls } = e.currentTarget.dataset
    wx.previewImage({ current: url, urls })
  },
  viewOrder(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({ url: `/pages/order/detail/detail?id=${id}` })
  }
})

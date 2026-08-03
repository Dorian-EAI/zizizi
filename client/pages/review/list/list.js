const api = require('../../../utils/request')

Page({
  data: {
    workerId: null,
    serviceType: null,
    reviews: [],
    stats: null,
    page: 1,
    size: 10,
    hasMore: true,
    loading: false,
    activeTag: '',
    tags: []
  },
  onLoad(options) {
    const { worker_id, service_type, title } = options
    this.setData({ workerId: worker_id || null, serviceType: service_type || null })
    if (title) wx.setNavigationBarTitle({ title: decodeURIComponent(title) })
    this.loadStats()
    this.loadReviews(true)
  },
  loadStats() {
    const params = {}
    if (this.data.workerId) params.worker_id = this.data.workerId
    if (this.data.serviceType) params.service_type = this.data.serviceType
    api.get('/api/reviews/stats', params).then(data => {
      const tags = (data.tag_counts || []).map(t => t.tag)
      this.setData({ stats: data, tags })
    }).catch(() => {})
  },
  loadReviews(reset = false) {
    if (this.data.loading) return
    if (!reset && !this.data.hasMore) return
    this.setData({ loading: true })
    const page = reset ? 1 : this.data.page
    const params = { page, size: this.data.size }
    if (this.data.workerId) params.worker_id = this.data.workerId
    if (this.data.serviceType) params.service_type = this.data.serviceType
    if (this.data.activeTag) params.tag = this.data.activeTag
    api.get('/api/reviews', params).then(data => {
      const list = data.list || []
      this.setData({
        reviews: reset ? list : this.data.reviews.concat(list),
        page: page + 1,
        hasMore: list.length === this.data.size,
        loading: false
      })
    }).catch(() => {
      this.setData({ loading: false })
    })
  },
  onReachBottom() {
    this.loadReviews()
  },
  onTagTap(e) {
    const tag = e.currentTarget.dataset.tag
    this.setData({ activeTag: this.data.activeTag === tag ? '' : tag })
    this.loadReviews(true)
  },
  onLikeTap(e) {
    const { id, index } = e.currentTarget.dataset
    api.post(`/api/reviews/${id}/like`).then(data => {
      const key = `reviews[${index}].liked`
      const countKey = `reviews[${index}].like_count`
      this.setData({ [key]: data.liked, [countKey]: data.like_count })
    }).catch(() => {})
  },
  previewImage(e) {
    const { url, urls } = e.currentTarget.dataset
    wx.previewImage({ current: url, urls })
  }
})

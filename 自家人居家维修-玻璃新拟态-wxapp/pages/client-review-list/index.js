const app = getApp()
const { createRuntimePage, displayTime, initial, listFrom, messageOf, stars } = require('../../utils/detail-page')

const STATUS_TEXT = { pending: '待审核', approved: '已公开', rejected: '未通过' }

function normalizeReview(raw) {
  const rating = Math.max(0, Math.min(5, Number(raw.rating) || 0))
  return Object.assign({}, raw, {
    avatarText: initial('师傅'),
    workerText: raw.worker_id ? '师傅 #' + raw.worker_id : '服务师傅',
    serviceText: raw.service_type || '未标注服务类型',
    orderText: raw.order_id ? '订单 #' + raw.order_id : '订单信息不可用',
    createdText: displayTime(raw.created_at, true),
    statusText: STATUS_TEXT[raw.status] || raw.status || '状态未知',
    starsText: stars(rating),
    tags: Array.isArray(raw.review_tags) ? raw.review_tags : [],
    images: Array.isArray(raw.review_images) ? raw.review_images : [],
    contentText: raw.review_content || '未填写文字评价',
    hasReply: Boolean(raw.worker_reply)
  })
}

Page(createRuntimePage({
  pageId: 'page-client-review-list',
  route: 'pages/client-review-list/index',
  source: 'pages/client-review-list.html',
  sourceHash: 'fnv1a-a1b5984b',
  title: '我的评价'
}, {
  data: {
    loading: true,
    loadError: '',
    reviews: [],
    filteredReviews: [],
    activeFilter: 'all',
    loadedCount: 0,
    serverTotal: 0,
    averageText: '0.0'
  },

  onLoad() {
    this.loadReviews()
  },

  async loadReviews() {
    this.setData({ loading: true, loadError: '' })
    try {
      const result = await app.getApi().reviews.mine({ page: 1, size: 50 })
      const reviews = listFrom(result).map(normalizeReview)
      const sum = reviews.reduce((total, item) => total + (Number(item.rating) || 0), 0)
      this.setData({
        loading: false,
        reviews,
        serverTotal: Number(result && result.total) || reviews.length,
        loadedCount: reviews.length,
        averageText: reviews.length ? (sum / reviews.length).toFixed(1) : '0.0'
      })
      this.applyFilter(this.data.activeFilter)
    } catch (error) {
      this.setData({ loading: false, loadError: messageOf(error), reviews: [], filteredReviews: [] })
    }
  },

  applyFilter(filter) {
    const reviews = this.data.reviews || []
    const filteredReviews = reviews.filter(item => {
      if (filter === 'image') return item.images.length > 0
      if (filter === 'replied') return item.hasReply
      return true
    })
    this.setData({ activeFilter: filter, filteredReviews })
  },

  onFilter(event) {
    this.applyFilter(event.currentTarget.dataset.filter || 'all')
  },

  onOpenReview(event) {
    const id = event.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: '/pages/client-review-detail/index?id=' + id })
  }
}))

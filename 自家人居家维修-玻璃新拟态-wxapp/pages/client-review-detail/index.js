const app = getApp()
const { createRuntimePage, displayTime, listFrom, messageOf, stars } = require('../../utils/detail-page')

const STATUS_TEXT = { pending: '待审核', approved: '已公开', rejected: '未通过' }

Page(createRuntimePage({
  pageId: 'page-client-review-detail',
  route: 'pages/client-review-detail/index',
  source: 'pages/client-review-detail.html',
  sourceHash: 'fnv1a-ebc6a9d3',
  title: '评价详情'
}, {
  data: { loading: true, loadError: '', review: null, images: [] },

  onLoad(query) {
    this.reviewId = String(query && (query.id || query.reviewId) || '')
    this.loadReview()
  },

  async loadReview() {
    if (!this.reviewId) {
      this.setData({ loading: false, loadError: '缺少评价标识', review: null })
      return
    }
    this.setData({ loading: true, loadError: '' })
    try {
      const result = await app.getApi().reviews.mine({ page: 1, size: 50 })
      const raw = listFrom(result).find(item => String(item.id) === this.reviewId)
      if (!raw) throw new Error('未找到可查看的评价记录')
      const review = Object.assign({}, raw, {
        workerText: raw.worker_id ? '师傅 #' + raw.worker_id : '服务师傅',
        serviceText: raw.service_type || '未标注服务类型',
        orderText: raw.order_id ? '#' + raw.order_id : '不可用',
        createdText: displayTime(raw.created_at, true),
        replyTimeText: displayTime(raw.worker_reply_at, true),
        statusText: STATUS_TEXT[raw.status] || raw.status || '状态未知',
        starsText: stars(raw.rating),
        contentText: raw.review_content || '未填写文字评价',
        tags: Array.isArray(raw.review_tags) ? raw.review_tags : []
      })
      this.setData({ loading: false, review, images: Array.isArray(raw.review_images) ? raw.review_images : [] })
    } catch (error) {
      this.setData({ loading: false, loadError: messageOf(error), review: null, images: [] })
    }
  },

  onPreview(event) {
    const index = Number(event.currentTarget.dataset.index) || 0
    const urls = this.data.images
    if (urls[index]) wx.previewImage({ current: urls[index], urls })
  }
}))

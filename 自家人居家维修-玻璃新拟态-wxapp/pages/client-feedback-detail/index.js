const app = getApp()
const { createRuntimePage, displayTime, listFrom, messageOf } = require('../../utils/detail-page')

const TYPE_TEXT = { suggestion: '建议', bug: 'Bug', complaint: '投诉', other: '其他' }
const STATUS_TEXT = { pending: '待处理', processing: '处理中', resolved: '已回复' }

Page(createRuntimePage({
  pageId: 'page-client-feedback-detail',
  route: 'pages/client-feedback-detail/index',
  source: 'pages/client-feedback-detail.html',
  sourceHash: 'fnv1a-e7b949e4',
  title: '反馈详情'
}, {
  data: { loading: true, loadError: '', item: null, images: [] },

  onLoad(query) {
    this.feedbackId = String(query && (query.id || query.feedbackId) || '')
    this.loadFeedback()
  },

  async loadFeedback() {
    this.setData({ loading: true, loadError: '' })
    try {
      const result = await app.getApi().feedback.mine({ page: 1, size: 100 })
      const items = listFrom(result)
      const raw = this.feedbackId
        ? items.find(entry => String(entry.id) === this.feedbackId)
        : items[0]
      if (!raw) throw new Error('未找到可查看的反馈记录')
      const item = Object.assign({}, raw, {
        numberText: 'FB' + String(raw.id).padStart(8, '0'),
        typeText: TYPE_TEXT[raw.type] || '其他',
        statusText: STATUS_TEXT[raw.status] || raw.status || '未知',
        createdText: displayTime(raw.created_at, true),
        replied: Boolean(raw.reply)
      })
      this.setData({ loading: false, item, images: Array.isArray(raw.images) ? raw.images : [] })
    } catch (error) {
      this.setData({ loading: false, loadError: messageOf(error), item: null, images: [] })
    }
  },

  onPreview(event) {
    const index = Number(event.currentTarget.dataset.index) || 0
    const urls = this.data.images
    if (urls[index]) wx.previewImage({ current: urls[index], urls })
  }
}))

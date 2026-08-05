const app = getApp()

const DOCUMENTS = {
  'user-agreement': { key: 'agreement', label: '用户协议' },
  agreement: { key: 'agreement', label: '用户协议' },
  'privacy-policy': { key: 'privacy', label: '隐私政策' },
  privacy: { key: 'privacy', label: '隐私政策' },
  'platform-rules': { key: 'platform-rules', label: '平台规则' },
  'service-terms': { key: 'service-terms', label: '服务条款' },
  'company-profile': { key: 'company-profile', label: '公司介绍' }
}

Page({
  data: {
    document: 'user-agreement',
    title: '用户协议',
    content: '',
    updatedText: '以运营发布版本为准',
    loading: true,
    loadError: false,
    fontMode: 'normal'
  },

  onLoad(query) {
    const document = query && query.document && DOCUMENTS[query.document] ? query.document : 'user-agreement'
    this.setData({ document })
    this.loadDocument(document)
  },

  normalizeContent(value) {
    return String(value || '')
      .replace(/^#{1,6}\s*/gm, '')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\[(.*?)\]\([^)]*\)/g, '$1')
      .replace(/^[-*]\s+/gm, '• ')
      .trim()
  },

  formatUpdatedAt(value) {
    if (!value) return '以运营发布版本为准'
    const raw = String(value)
    const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(raw) ? raw : raw + 'Z')
    if (Number.isNaN(date.getTime())) return '以运营发布版本为准'
    const pad = number => String(number).padStart(2, '0')
    return '更新于 ' + date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate())
  },

  async loadDocument(document) {
    const meta = DOCUMENTS[document] || DOCUMENTS['user-agreement']
    this.setData({ loading: true, loadError: false, title: meta.label, document })
    try {
      const pages = app.getApi().pages
      let payload
      if (meta.key === 'agreement') payload = await pages.agreement()
      else if (meta.key === 'privacy') payload = await pages.privacy()
      else payload = await pages.byKey(meta.key)
      const content = this.normalizeContent(payload && payload.content)
      if (!content) throw new Error('运营尚未发布该文档')
      this.setData({
        title: (payload && payload.title) || meta.label,
        content,
        updatedText: this.formatUpdatedAt(payload && payload.updated_at),
        loading: false
      })
    } catch (error) {
      console.error('加载协议文档失败', error)
      this.setData({ loading: false, loadError: true, content: '', updatedText: (error && error.message) || '文档加载失败' })
    }
  },

  onTab(event) {
    const document = event.currentTarget.dataset.document
    if (DOCUMENTS[document] && document !== this.data.document) this.loadDocument(document)
  },

  onFontSize() {
    const next = this.data.fontMode === 'normal' ? 'large' : (this.data.fontMode === 'large' ? 'small' : 'normal')
    this.setData({ fontMode: next })
  },

  onRetry() { this.loadDocument(this.data.document) },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

// pages/client-service-detail/index.js — 服务详情页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { resolveAssetUrl } = require('../../utils/format')

Page({
  data: {
    statusBarHeight: 20,
    serviceKey: '',
    service: null,
    banner: '',
    steps: [],
    priceItems: [],
    faqs: [],
    gallery: [],
    cases: [],
    detailSections: [],
    previewImages: [],
    workers: [],
    reviews: [],
    reviewSummary: null,
    relatedLoading: true,
    favoriteWorkerId: '',
    openedFaq: -1,
    isFavorited: false,
    icons: {}
  },

  onLoad(query) {
    const serviceKey = query.serviceKey || ''
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      serviceKey,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        heart: buildIcon('heart', COLORS.text2),
        heartActive: buildIcon('heart', COLORS.accent),
        star: buildIcon('star', COLORS.accent),
        clock: buildIcon('clock', COLORS.text3),
        arrowDown: buildIcon('arrowRight', COLORS.text3),
        check: buildIcon('check', COLORS.white),
        droplet: buildIcon('droplet', COLORS.brand),
        message: buildIcon('message', COLORS.text2)
      }
    })
    this.loadDetail(serviceKey)
  },

  async loadDetail(serviceKey) {
    const api = app.getApi()
    try {
      const detail = await api.services.detail(serviceKey)
      const rawService = detail || {}
      const service = Object.assign({}, rawService)
      // 服务流程：后端字段 process_steps（每项 {step,title,desc}），前端旧字段 steps
      const rawSteps = service.process_steps != null ? service.process_steps : (service.steps || [])
      const steps = rawSteps.map((s, i) => ({
        index: i + 1,
        title: s.title || s.name || '',
        desc: s.desc || s.description || ''
      }))
      // 只展示后端已配置的价格明细，不在客户端拆分虚构费用。
      let priceItems = Array.isArray(service.price_details)
        ? service.price_details.map(item => ({
            label: item.label || item.name || '价格项',
            amount: item.amount != null ? item.amount : item.price,
            note: item.note || item.description || ''
          })).filter(item => item.amount != null)
        : []
      if (!priceItems.length && (Number(service.price_min) > 0 || Number(service.price_max) > 0)) {
        const min = Number(service.price_min) || 0
        const max = Number(service.price_max) || min
        priceItems = [{
          label: '参考价格',
          amount: min === max ? String(min) : (min + '-' + max),
          note: '单位：/' + (service.price_unit || '次')
        }]
      }
      // FAQ：后端字段 faq（每项 {q,a}），前端旧字段 faqs
      const faqs = service.faq != null ? service.faq : (service.faqs || [])

      // 后台配置的图片：相对路径（/uploads/...）统一转换为完整 URL
      const rawGallery = (Array.isArray(service.service_images) ? service.service_images : [])
        .map((item, index) => {
          const source = typeof item === 'string' ? { url: item } : (item || {})
          return {
            url: source.url || '',
            caption: source.caption || '',
            sort: Number(source.sort) || index + 1
          }
        })
        .filter(item => item.url)
        .sort((a, b) => a.sort - b.sort)
      const gallery = rawGallery.map(item => ({
        url: resolveAssetUrl(item.url),
        caption: item.caption
      }))

      const cases = (Array.isArray(service.cases) ? service.cases : [])
        .map(item => {
          const source = item || {}
          return {
            title: source.title || '服务案例',
            desc: source.desc || source.description || '',
            images: (Array.isArray(source.images) ? source.images : [])
              .filter(Boolean)
              .map(resolveAssetUrl)
          }
        })
        .filter(item => item.title || item.desc || item.images.length)

      const detailSections = (Array.isArray(service.detail_sections) ? service.detail_sections : [])
        .map(item => {
          const source = item || {}
          return {
            title: source.title || '',
            content: source.content || '',
            image: source.image ? resolveAssetUrl(source.image) : ''
          }
        })
        .filter(item => item.title || item.content || item.image)

      const previewImages = []
        .concat(gallery.map(item => item.url))
        .concat(cases.reduce((all, item) => all.concat(item.images), []))
        .concat(detailSections.map(item => item.image).filter(Boolean))

      this.setData({
        service,
        banner: resolveAssetUrl(service.banner || ''),
        steps,
        priceItems,
        faqs,
        gallery,
        cases,
        detailSections,
        previewImages
      })
      await this.loadRelated(service.key || serviceKey)
    } catch (e) {
      console.error('加载服务详情失败', e)
      this.setData({
        service: null,
        banner: '',
        steps: [],
        priceItems: [],
        faqs: [],
        gallery: [],
        cases: [],
        detailSections: [],
        previewImages: [],
        workers: [],
        reviews: [],
        relatedLoading: false
      })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  async loadRelated(serviceKey) {
    const api = app.getApi()
    this.setData({ relatedLoading: true })
    const settle = promise => promise
      .then(value => ({ fulfilled: true, value }))
      .catch(error => ({ fulfilled: false, error }))
    const [workersResult, reviewsResult, statsResult] = await Promise.all([
      settle(api.services.workers({ service_key: serviceKey, limit: 6 })),
      settle(api.reviews.list({ service_type: serviceKey, page: 1, size: 4 })),
      settle(api.reviews.stats({ service_type: serviceKey }))
    ])
    const rawWorkers = workersResult.fulfilled && Array.isArray(workersResult.value)
      ? workersResult.value
      : []
    const workers = rawWorkers.map(worker => ({
      id: worker.id,
      name: worker.name || worker.nickname || '师傅',
      avatar: worker.avatar || '',
      avatarText: String(worker.name || worker.nickname || '师').slice(0, 1),
      certified: Number(worker.certified) === 2,
      ratingText: worker.rating != null ? String(worker.rating) : '—',
      serviceCountText: worker.service_count != null ? String(worker.service_count) : '—'
    }))
    const reviewsPayload = reviewsResult.fulfilled ? reviewsResult.value : null
    const rawReviews = Array.isArray(reviewsPayload)
      ? reviewsPayload
      : ((reviewsPayload && (reviewsPayload.list || reviewsPayload.items)) || [])
    const reviews = rawReviews.map(review => {
      const rating = Math.max(0, Math.min(5, Number(review.rating) || 0))
      return {
        id: review.id,
        displayName: review.is_anonymous ? '匿名用户' : '平台用户',
        avatarText: review.is_anonymous ? '匿' : '用',
        stars: '★'.repeat(rating) + '☆'.repeat(5 - rating),
        date: this.formatDate(review.created_at),
        content: review.review_content || '用户未填写文字评价'
      }
    })
    const stats = statsResult.fulfilled ? statsResult.value : null
    const reviewSummary = stats && stats.total_count != null
      ? {
          total: Number(stats.total_count) || 0,
          average: stats.avg_rating != null ? String(stats.avg_rating) : '—'
        }
      : null
    this.setData({ workers, reviews, reviewSummary, relatedLoading: false })
  },

  formatDate(value) {
    if (!value) return ''
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return String(value).slice(0, 10)
    const pad = number => String(number).padStart(2, '0')
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate())
  },

  onWorkerTap(e) {
    const id = e.currentTarget.dataset.id
    const worker = this.data.workers.find(item => String(item.id) === String(id))
    if (!worker) return
    this.setData({ favoriteWorkerId: worker.id })
    wx.showModal({
      title: worker.name,
      content: '评分：' + worker.ratingText + '\n服务次数：' + worker.serviceCountText + '\n认证状态：' + (worker.certified ? '已认证' : '未认证'),
      showCancel: false,
      confirmColor: '#0D9488'
    })
  },

  onPreviewImage(e) {
    const url = e.currentTarget.dataset.url
    if (!url) return
    const urls = this.data.previewImages && this.data.previewImages.length
      ? this.data.previewImages
      : [url]
    wx.previewImage({ current: url, urls })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onContactService() {
    wx.navigateTo({ url: '/package-client/pages/client-service/index' })
  },

  onToggleFaq(e) {
    const idx = e.currentTarget.dataset.idx
    this.setData({ openedFaq: this.data.openedFaq === idx ? -1 : idx })
  },

  async onToggleFavorite() {
    const api = app.getApi()
    const workerId = this.data.favoriteWorkerId
    if (!workerId) {
      wx.showToast({ title: '请先选择一位师傅', icon: 'none' })
      return
    }
    try {
      const result = await api.favorite.toggleWorker(workerId)
      let isFavorited = result && typeof result.is_favorite === 'boolean'
        ? result.is_favorite
        : (result && typeof result.favorited === 'boolean' ? result.favorited : null)
      if (isFavorited == null) {
        const state = await api.favorite.existsWorker(workerId)
        isFavorited = !!(state && (state.exists === true || state.is_favorite === true))
      }
      this.setData({ isFavorited })
      wx.showToast({ title: isFavorited ? '已收藏' : '已取消', icon: 'none' })
    } catch (e) {
      console.error('收藏失败', e)
    }
  },

  onPublish() {
    const key = this.data.serviceKey
    wx.navigateTo({ url: '/pages/client-publish/index?serviceKey=' + key })
  }
})

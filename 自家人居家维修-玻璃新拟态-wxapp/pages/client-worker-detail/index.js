const app = getApp()

function parseList(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (!value) return []
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) return parsed.filter(Boolean)
    } catch (error) {}
    return value.split(/[,，;；|]/).map(item => item.trim()).filter(Boolean)
  }
  return []
}

Page({
  data: {
    workerId: '',
    worker: null,
    services: [],
    reviews: [],
    reviewCount: 0,
    loading: true,
    loadError: '',
    favorite: false,
    favoriteBusy: false
  },

  onLoad(query) {
    const workerId = String(query && (query.workerId || query.id) || '')
    this.setData({ workerId })
    this.loadData()
  },

  async loadData() {
    if (!/^\d+$/.test(this.data.workerId)) {
      this.setData({ loading: false, loadError: '缺少有效师傅标识' })
      return
    }
    this.setData({ loading: true, loadError: '' })
    try {
      const api = app.getApi()
      const results = await Promise.all([
        api.services.workerDetail(this.data.workerId),
        api.reviews.workerDetail(this.data.workerId).catch(() => null),
        api.favorite.existsWorker(this.data.workerId).catch(() => null)
      ])
      const basic = results[0] || {}
      const detail = results[1] || {}
      const stats = detail.stats || {}
      const services = parseList(detail.service_types || basic.skills).map((item, index) => ({
        id: index,
        name: typeof item === 'string' ? item : (item.name || item.key || '服务项目')
      }))
      const reviews = (Array.isArray(detail.recent_reviews) ? detail.recent_reviews : []).map(item => ({
        id: item.id,
        ratingText: '★'.repeat(Math.max(0, Math.min(5, Number(item.rating || 0)))),
        content: item.review_content || '用户未填写文字评价',
        tags: Array.isArray(item.review_tags) ? item.review_tags : []
      }))
      const name = detail.name || basic.name || '师傅'
      this.setData({
        worker: Object.assign({}, basic, detail, {
          name,
          initial: name.slice(0, 1),
          ratingText: Number(detail.rating != null ? detail.rating : basic.rating || 0).toFixed(1),
          completedText: String(detail.completed_orders != null ? detail.completed_orders : basic.completed_orders || 0),
          areaText: basic.service_area || '服务区域以预约结果为准',
          certifiedText: Number(basic.certified != null ? basic.certified : detail.certified) === 2 ? '实名认证' : '认证状态不可用'
        }),
        services,
        reviews,
        reviewCount: Number(stats.total_count || 0),
        favorite: !!(results[2] && (results[2].exists || results[2].is_favorite)),
        loading: false
      })
    } catch (error) {
      console.error('加载师傅详情失败', error)
      this.setData({ loading: false, loadError: (error && error.message) || '师傅详情加载失败' })
    }
  },

  async onFavorite() {
    if (this.data.favoriteBusy) return
    this.setData({ favoriteBusy: true })
    try {
      const result = await app.getApi().favorite.toggleWorker(this.data.workerId)
      const favorite = result && (result.exists != null ? result.exists : result.is_favorite)
      this.setData({ favorite: favorite == null ? !this.data.favorite : !!favorite })
    } catch (error) {
      wx.showToast({ title: (error && error.message) || '收藏操作失败', icon: 'none' })
    } finally {
      this.setData({ favoriteBusy: false })
    }
  },

  onPublish(e) {
    const service = e.currentTarget.dataset.service || ''
    const query = '?workerId=' + encodeURIComponent(this.data.workerId) + (service ? '&serviceType=' + encodeURIComponent(service) : '')
    wx.navigateTo({ url: '/pages/client-publish/index' + query })
  },

  onReviews() {
    wx.navigateTo({ url: '/pages/client-review-list/index?workerId=' + encodeURIComponent(this.data.workerId) })
  },

  onContact() {
    wx.showToast({ title: '联系方式仅在已指派订单中开放', icon: 'none' })
  },
  onRetry() { this.loadData() },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

// pages/client-service-detail/index.js — 服务详情页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    serviceKey: '',
    service: null,
    steps: [],
    priceItems: [],
    faqs: [],
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
      const service = detail || {}
      // 服务流程：后端字段 process_steps（每项 {step,title,desc}），前端旧字段 steps
      const rawSteps = service.process_steps != null ? service.process_steps : (service.steps || [])
      const steps = rawSteps.map((s, i) => ({
        index: i + 1,
        title: s.title || s.name || '',
        desc: s.desc || s.description || ''
      }))
      // 价格明细：后端字段 price_details（种子数据未填充→null），兜底用 price_min
      const priceItems = service.price_details != null ? service.price_details : (service.priceItems || [
        { label: '服务费', amount: service.price_min || service.serviceFee || 0 },
        { label: '材料费', amount: service.materialFee || 0, note: '按实结算' },
        { label: '上门费', amount: service.visitFee || 0 }
      ])
      // FAQ：后端字段 faq（每项 {q,a}），前端旧字段 faqs
      const faqs = service.faq != null ? service.faq : (service.faqs || [])
      this.setData({ service, steps, priceItems, faqs })
    } catch (e) {
      console.error('加载服务详情失败', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onContactService() {
    wx.navigateTo({ url: '/pages/client-service/index' })
  },

  onToggleFaq(e) {
    const idx = e.currentTarget.dataset.idx
    this.setData({ openedFaq: this.data.openedFaq === idx ? -1 : idx })
  },

  async onToggleFavorite() {
    const api = app.getApi()
    const workerId = this.data.service && this.data.service.recommendWorkerId
    if (!workerId) {
      wx.showToast({ title: '当前服务未关联可收藏师傅', icon: 'none' })
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

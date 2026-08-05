const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const HISTORY_KEY = '__CLIENT_SERVICE_SEARCH_HISTORY__'

function normalizeArray(value) {
  return Array.isArray(value) ? value : []
}

Page({
  data: {
    keyword: '',
    hotTags: [],
    history: [],
    services: [],
    workers: [],
    loading: false,
    searched: false,
    loadError: '',
    icons: {
      back: buildIcon('arrowLeft', COLORS.text1),
      search: buildIcon('search', COLORS.brand),
      droplet: buildIcon('droplet', COLORS.brand),
      appliance: buildIcon('appliance', COLORS.accentDark),
      user: buildIcon('user', COLORS.brand)
    }
  },

  onLoad(query) {
    this.loadHistory()
    this.loadHotTags()
    const keyword = String(query && query.keyword || '').trim().slice(0, 40)
    if (keyword) {
      this.setData({ keyword })
      this.search()
    }
  },

  loadHistory() {
    try {
      const value = wx.getStorageSync(HISTORY_KEY)
      this.setData({ history: Array.isArray(value) ? value.filter(Boolean).slice(0, 8) : [] })
    } catch (error) {
      this.setData({ history: [] })
    }
  },

  async loadHotTags() {
    try {
      const tags = await app.getApi().services.hotTags()
      this.setData({ hotTags: normalizeArray(tags).map(String).filter(Boolean).slice(0, 12) })
    } catch (error) {
      console.warn('加载热搜词失败', error)
    }
  },

  onInput(e) {
    this.setData({ keyword: String(e.detail.value || '').slice(0, 40) })
  },

  onTag(e) {
    this.setData({ keyword: String(e.currentTarget.dataset.keyword || '') })
    this.search()
  },

  async search() {
    const keyword = String(this.data.keyword || '').trim()
    if (!keyword) {
      wx.showToast({ title: '请输入搜索内容', icon: 'none' })
      return
    }
    if (this.data.loading) return
    this.setData({ loading: true, searched: true, loadError: '' })
    try {
      const result = await app.getApi().services.search(keyword)
      const services = normalizeArray(result && result.services).map(item => Object.assign({}, item, {
        initial: String(item.name || '服').slice(0, 1),
        priceText: item.price_min != null ? ('¥' + Number(item.price_min).toFixed(0) + ' 起') : '价格以详情为准'
      }))
      const workers = normalizeArray(result && result.workers).map(item => Object.assign({}, item, {
        initial: String(item.name || '师').slice(0, 1)
      }))
      const history = [keyword].concat(this.data.history.filter(item => item !== keyword)).slice(0, 8)
      try { wx.setStorageSync(HISTORY_KEY, history) } catch (error) { console.warn('保存搜索历史失败', error) }
      this.setData({ services, workers, history, loading: false })
    } catch (error) {
      console.error('搜索失败', error)
      this.setData({ services: [], workers: [], loading: false, loadError: (error && error.message) || '搜索失败' })
    }
  },

  onClearHistory() {
    try { wx.removeStorageSync(HISTORY_KEY) } catch (error) { console.warn('清空搜索历史失败', error) }
    this.setData({ history: [] })
  },

  onService(e) {
    const key = e.currentTarget.dataset.key
    if (key) wx.navigateTo({ url: '/pages/client-service-detail/index?key=' + encodeURIComponent(key) })
  },

  onWorker(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: '/pages/client-worker-detail/index?workerId=' + encodeURIComponent(id) })
  },

  onBack() { wx.navigateBack({ delta: 1 }) }
})

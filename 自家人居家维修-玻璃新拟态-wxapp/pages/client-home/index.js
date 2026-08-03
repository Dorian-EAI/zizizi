// pages/client-home/index.js — 客户端首页 像素级复刻 zjrnew.DESIGN
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { greeting } = require('../../utils/format')

Page({
  data: {
    greeting: '',
    statusBarHeight: 20,
    // 滚动变形状态（阈值：20/40/60/90px，忠于 HTML 参考脚本）
    scrolled: false,
    scrolled2: false,
    titleBarVisible: false,
    titleBarSearchMode: false,
    // 服务列表（由 API 加载，附加图标 data URI）
    services: [],
    // 推荐师傅（由 API 加载）
    workers: [],
    // 分类筛选 Chips（HTML 参考：全部/防水维修/漏水检测/水电改造/清洁服务/厨房改造）
    categories: ['全部', '防水维修', '漏水检测', '水电改造', '清洁服务', '厨房改造'],
    activeCat: 0,
    // 统计卡片数据（HTML 参考：8,247 认证师傅 / 98.6% 好评率 / 3s 平均响应）
    stats: [
      { key: 'masters', value: '—', label: '认证师傅' },
      { key: 'rating', value: '—', label: '好评率' },
      { key: 'response', value: '—', label: '平均响应' }
    ],
    // 推荐服务横滑卡片（HTML 参考：3 张卡片，彩色图块）
    recommendServices: [],
    icons: {}
  },

  onLoad() {
    this.setData({
      greeting: greeting(),
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        search: buildIcon('search', COLORS.text3),
        bot: buildIcon('bot', '#FFFFFF'),
        star: buildIcon('star', COLORS.accent)
      }
    })
    this.loadData()
  },

  onShow() {
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
  },

  async loadData() {
    const api = app.getApi()
    try {
      const [services, workers, platformStats] = await Promise.all([
        api.getServices(),
        api.getWorkers(),
        api.getPlatformStats()
      ])
      const servicesWithIcons = services.map(s => ({
        ...s,
        iconUrl: buildIcon(s.icon, COLORS.brand)
      }))
      const workersWithIcons = workers.map(w => ({
        ...w,
        avatarUrl: buildIcon('user', '#6B8F71')
      }))
      const gradients = [
        'linear-gradient(135deg, #0A7A70 0%, #0D9488 50%, #14B8A6 100%)',
        'linear-gradient(135deg, #A0723C 0%, #D4944C 50%, #E8C088 100%)',
        'linear-gradient(135deg, #4A7A5A 0%, #5B8C5A 50%, #8ABB8A 100%)'
      ]
      const recommendServices = servicesWithIcons.slice(0, 3).map((service, index) => ({
        key: service.key,
        name: service.name,
        gradient: gradients[index],
        rating: platformStats.average_rating ? Number(platformStats.average_rating).toFixed(1) : '—',
        count: platformStats.certified_worker_count || 0,
        price: Number(service.price_min || 0)
      }))
      const responseSeconds = platformStats.average_response_seconds
      const responseText = responseSeconds == null
        ? '—'
        : (responseSeconds < 60 ? (responseSeconds + 's') : (Math.round(responseSeconds / 60) + 'min'))
      this.setData({
        services: servicesWithIcons,
        workers: workersWithIcons,
        recommendServices,
        stats: [
          { key: 'masters', value: String(platformStats.certified_worker_count || 0), label: '认证师傅' },
          { key: 'rating', value: platformStats.satisfaction_rate == null ? '—' : (platformStats.satisfaction_rate + '%'), label: '好评率' },
          { key: 'response', value: responseText, label: '平均响应' }
        ]
      })
    } catch (e) {
      console.error('加载数据失败', e)
    }
  },

  // ===== 滚动监听：驱动标题栏变形 + Hero 渐隐 =====
  // 阈值忠于 HTML 参考脚本：
  // y>40 → titleBar.visible；y>90 → titleBar.search-mode
  // y>20 → scrolled（greeting 渐隐）；y>60 → scrolled-2（app-name/search-bar 渐隐）
  onPageScroll(e) {
    const y = e.detail.scrollTop
    const scrolled = y > 20
    const scrolled2 = y > 60
    const titleBarVisible = y > 40
    const titleBarSearchMode = y > 90

    // 仅在状态变化时 setData，避免频繁渲染
    const d = this.data
    if (d.scrolled !== scrolled || d.scrolled2 !== scrolled2 ||
        d.titleBarVisible !== titleBarVisible || d.titleBarSearchMode !== titleBarSearchMode) {
      this.setData({ scrolled, scrolled2, titleBarVisible, titleBarSearchMode })
    }
  },

  onSearch() {
    wx.navigateTo({ url: '/pages/search/index' })
  },

  onServiceTap(e) {
    const key = e.currentTarget.dataset.key
    wx.navigateTo({ url: '/pages/client-publish/index?serviceKey=' + key })
  },

  onCatTap(e) {
    this.setData({ activeCat: e.currentTarget.dataset.index })
  },

  onWorkerTap(e) {
    const id = e.currentTarget.dataset.id
    wx.showToast({ title: '查看师傅详情', icon: 'none' })
  },

  onRecTap(e) {
    const index = e.currentTarget.dataset.index
    const service = this.data.recommendServices[index]
    if (service) wx.navigateTo({ url: '/pages/client-publish/index?serviceKey=' + service.key })
  },

  onRecBook(e) {
    const index = e.currentTarget.dataset.index
    const service = this.data.recommendServices[index]
    if (service) wx.navigateTo({ url: '/pages/client-publish/index?serviceKey=' + service.key })
  },

  onPublish() {
    wx.redirectTo({ url: '/pages/client-publish/index' })
  },

  onAiTap() {
    wx.navigateTo({ url: '/pages/client-chat/index' })
  }
})

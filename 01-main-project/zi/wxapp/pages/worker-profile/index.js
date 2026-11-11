// pages/worker-profile/index.js — 师傅端个人中心 像素级复刻 worker-profile.html
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const BLUE = '#5A8FAD'

Page({
  data: {
    statusBarHeight: 20,
    workerInfo: {
      name: '未完善资料',
      rating: '—',
      serviceTimes: 0,
      completedOrders: 0,
      praiseRate: '—',
      serviceScope: '待完善',
      yearsExp: '—',
      area: '待完善',
      verifyStatus: '未认证',
      certified: false,
      avatarUrl: ''
    },
    basicInfo: [],
    features: [],
    icons: {},
    navScrolled: false
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        edit: buildIcon('edit', COLORS.brandWorker),
        verify: buildIcon('shield', COLORS.brandWorker),
        star: buildIcon('star', COLORS.accent),
        chevron: buildIcon('chevronRight', COLORS.text3)
      }
    })
    this.initBasicInfo()
    this.initFeatures()
    this.loadWorkerInfo()
  },

  onShow() {
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
  },

  // 滚动驱动 hero 收缩变形（参考 小程序动画与布局实现规范.md 第二章）
  onScroll(e) {
    const scrollTop = e.detail.scrollTop
    const shouldScroll = scrollTop > 40
    if (shouldScroll !== this.data.navScrolled) {
      this.setData({ navScrolled: shouldScroll })
    }
  },

  // 基本信息 4 行：服务范围/从业年限/所在区域/认证状态（彩色圆角方图标）
  initBasicInfo() {
    const w = this.data.workerInfo
    const rows = [
      { key: 'scope', icon: 'carpentry', tone: 'teal', color: COLORS.brandWorker, label: '服务范围', value: w.serviceScope, valueTone: false },
      { key: 'experience', icon: 'clock', tone: 'amber', color: COLORS.accent, label: '从业年限', value: w.yearsExp === '—' ? '—' : (w.yearsExp + '年'), valueTone: false },
      { key: 'area', icon: 'location', tone: 'blue', color: BLUE, label: '所在区域', value: w.area, valueTone: false },
      { key: 'verify', icon: 'shield', tone: 'green', color: COLORS.green, label: '认证状态', value: w.verifyStatus, valueTone: true }
    ].map(r => Object.assign({}, r, { iconUrl: buildIcon(r.icon, r.color) }))
    this.setData({ basicInfo: rows })
  },

  // 更多功能 4 项：我的评价/收入报告/帮助与反馈/设置
  initFeatures() {
    const features = [
      { key: 'reviews', name: '我的评价', icon: 'star', tone: 'purple', color: COLORS.purple },
      { key: 'income', name: '收入报告', icon: 'trending-up', tone: 'blue', color: BLUE },
      { key: 'help', name: '帮助与反馈', icon: 'message', tone: 'green', color: COLORS.green },
      { key: 'settings', name: '设置', icon: 'settings', tone: 'gray', color: COLORS.text2 }
    ].map(f => Object.assign({}, f, { iconUrl: buildIcon(f.icon, f.color) }))
    this.setData({ features })
  },

  async loadWorkerInfo() {
    const api = app.getApi()
    try {
      const info = await api.getWorkerInfo()
      // 后端 /api/auth/worker/me 返回 snake_case，需映射为前端 workerInfo 形状
      const certifiedMap = { 0: '未认证', 1: '审核中', 2: '已认证', 3: '未通过' }
      const serviceTypes = info.service_types
      const scope = Array.isArray(serviceTypes)
        ? serviceTypes.join(' · ')
        : (serviceTypes || info.serviceScope || '待完善')
      const mapped = {
        name: info.real_name || info.nickname || info.name || '未完善资料',
        rating: info.rating != null ? info.rating : '—',
        serviceTimes: info.service_count != null ? info.service_count
          : (info.total_orders != null ? info.total_orders : 0),
        completedOrders: info.completed_orders != null ? info.completed_orders
          : (info.completedOrders != null ? info.completedOrders : 0),
        serviceScope: scope,
        area: info.service_area || info.area || '待完善',
        verifyStatus: certifiedMap[info.certified] || '未认证',
        certified: Number(info.certified) === 2,
        avatarUrl: info.avatar || buildIcon('user', COLORS.brandWorker)
      }
      this.setData({
        workerInfo: Object.assign({}, this.data.workerInfo, mapped)
      })
      this.initBasicInfo()
    } catch (e) {
      console.error('加载师傅信息失败', e)
      this.setData({
        'workerInfo.avatarUrl': buildIcon('user', COLORS.brandWorker)
      })
    }
  },

  onEdit() {
    wx.showToast({ title: '资料编辑接口暂未开放', icon: 'none' })
  },

  onInfoTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'verify') {
      wx.navigateTo({ url: '/package-worker/pages/worker-certification/index' })
      return
    }
    const item = this.data.basicInfo.find(row => row.key === key)
    if (!item) return
    wx.showModal({
      title: item.label,
      content: String(item.value || '暂无资料'),
      showCancel: false,
      confirmColor: '#2D6CDF'
    })
  },

  onFeatureTap(e) {
    const key = e.currentTarget.dataset.key
    const routes = {
      reviews: '/package-worker/pages/worker-reviews/index',
      income: '/package-worker/pages/worker-transactions/index',
      help: '/package-worker/pages/worker-appeal/index',
      settings: '/package-worker/pages/worker-settings/index'
    }
    if (routes[key]) {
      wx.navigateTo({ url: routes[key] })
    } else {
      wx.showToast({ title: '该功能入口暂未开放', icon: 'none' })
    }
  }
})

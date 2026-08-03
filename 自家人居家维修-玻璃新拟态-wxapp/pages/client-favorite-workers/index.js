// pages/client-favorite-workers/index.js — 收藏师傅页（像素级复刻 client-favorite-workers.html）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    tabs: [
      { key: 'all', name: '全部' },
      { key: 'water', name: '水电' },
      { key: 'appliance', name: '家电' },
      { key: 'pipe', name: '管道' }
    ],
    activeFilter: 'all',
    workers: [],
    allWorkers: [],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        edit: buildIcon('menu', COLORS.text1),
        star: buildIcon('star', COLORS.accent),
        location: buildIcon('location', COLORS.text2),
        heart: buildIcon('heart', COLORS.brand),
        shield: buildIcon('shield', COLORS.green),
        check: buildIcon('check', COLORS.green)
      }
    })
  },

  onShow() {
    this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    try {
      const list = await api.favorite.listWorkers()
      const details = await Promise.all((list || []).map(async worker => {
        const workerId = worker.worker_id != null ? worker.worker_id : worker.id
        if (!workerId) return worker
        try {
          const detail = await api.favorite.getWorker(workerId)
          return Object.assign({}, worker, detail || {}, { worker_id: workerId })
        } catch (error) {
          console.error('加载收藏师傅详情失败', error)
          return worker
        }
      }))
      const allWorkers = details.map(w => this._mapWorker(w))
      this.setData({ allWorkers: allWorkers })
      this.applyFilter()
    } catch (e) {
      console.error('加载收藏失败', e)
      this.setData({ allWorkers: [], workers: [] })
    }
  },

  // 同步 HTML 参考字段：头像文字、等级文案/样式、距离、服务次数、技能、认证
  _mapWorker(w) {
    // 后端 list_favorites 返回 worker_id/nickname/service_count，前端用 id/name/serviceTimes
    const id = w.worker_id != null ? w.worker_id : w.id
    const name = w.real_name || w.nickname || w.name || '师傅'
    const level = Number(w.level) || 0
    const levelText = w.levelText || (level >= 4 ? '金牌师傅' : (level > 0 ? ('等级 ' + level) : ''))
    const isGold = levelText.indexOf('金') >= 0
    return Object.assign({}, w, {
      id: id,
      name: name,
      avatarText: (name || '师').charAt(0),
      levelText,
      levelClass: isGold ? 'gold' : 'normal',
      distanceText: (w.distance != null) ? (w.distance + 'km') : '',
      orderCount: w.service_count != null ? w.service_count : (w.serviceTimes != null ? w.serviceTimes : (w.orderCount || 0)),
      skills: w.skills || w.tags || [],
      verified: w.verified === true || w.certified === true || Number(w.certified) === 2,
      depositPaid: w.depositPaid === true || w.deposit_paid === true
    })
  },

  onFilterTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeFilter) return
    this.setData({ activeFilter: key })
    this.applyFilter()
  },

  applyFilter() {
    const key = this.data.activeFilter
    const all = this.data.allWorkers
    if (key === 'all') {
      this.setData({ workers: all })
      return
    }
    const kwMap = { water: '水电', appliance: '家电', pipe: '管道' }
    const kw = kwMap[key]
    const workers = all.filter(w => {
      const skills = w.skills || []
      if (skills.some(s => s.indexOf(kw) >= 0)) return true
      return (w.skill || '').indexOf(kw) >= 0
    })
    this.setData({ workers: workers })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onEdit() {
    wx.showToast({ title: '请在师傅卡片中直接取消收藏', icon: 'none' })
  },

  async onCancelFavorite(e) {
    const id = e.currentTarget.dataset.id
    const api = app.getApi()
    wx.showModal({
      title: '取消收藏',
      content: '确定要取消收藏该师傅吗？',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await api.favorite.toggleWorker(id)
          const workers = this.data.workers.filter(w => w.id !== id)
          const allWorkers = this.data.allWorkers.filter(w => w.id !== id)
          this.setData({ workers: workers, allWorkers: allWorkers })
          wx.showToast({ title: '已取消收藏', icon: 'none' })
        } catch (e) {
          console.error('取消收藏失败', e)
          wx.showToast({ title: '操作失败', icon: 'none' })
        }
      }
    })
  },

  onPublish(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/client-publish/index?workerId=' + id })
  }
})

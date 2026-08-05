// pages/client-member/index.js — 会员中心 像素级复刻 client-member.html
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    growthPercent: 0,
    member: {
      name: '微信用户',
      level: '普通会员',
      growth: 0,
      growthTarget: 0,
      growthHint: '会员信息待加载'
    },
    benefits: [],
    levelTiers: [],
    tasks: [],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        user: buildIcon('user', COLORS.brand)
      }
    })
  },

  onShow() {
    this.loadMember()
  },

  async loadMember() {
    if (this._loadingMember) return
    this._loadingMember = true
    const api = app.getApi()
    try {
      const detail = await api.member.detail()
      if (!detail || typeof detail !== 'object') throw new Error('会员信息响应无效')

      let levels = []
      try {
        const result = await api.member.benefits()
        levels = Array.isArray(result) ? result : ((result && result.items) || [])
      } catch (error) {
        console.error('加载会员等级失败', error)
      }

      let userInfo = app.globalData.userInfo || {}
      try {
        const response = await api.auth.me()
        const remote = response && response.user ? response.user : response
        if (remote && typeof remote === 'object') userInfo = remote
      } catch (error) {
        console.error('加载会员昵称失败，使用登录缓存', error)
      }

      this.applyMember(detail, levels, userInfo)
    } catch (error) {
      console.error('加载会员信息失败', error)
      this.setData({
        growthPercent: 0,
        member: {
          name: '微信用户',
          level: '普通会员',
          growth: 0,
          growthTarget: 0,
          growthHint: '会员信息加载失败'
        },
        benefits: [],
        levelTiers: []
      })
    } finally {
      this._loadingMember = false
    }
  },

  applyMember(detail, levels, userInfo) {
    const levelInfo = detail.level_info || {}
    const growth = Number(levelInfo.growth != null ? levelInfo.growth : detail.growth_value) || 0
    const nextGrowth = Number(levelInfo.next_level_growth) || 0
    const growthTarget = Math.max(growth, nextGrowth)
    const progress = Number(levelInfo.progress_percent)
    const growthPercent = Number.isFinite(progress)
      ? Math.max(0, Math.min(100, Math.round(progress)))
      : (growthTarget > 0 ? Math.min(100, Math.round(growth / growthTarget * 100)) : 0)
    const remaining = Math.max(0, growthTarget - growth)
    const benefits = this.mapBenefits(detail.benefits)
    const levelTiers = this.mapLevels(levels, levelInfo.level)

    this.setData({
      growthPercent,
      member: {
        name: userInfo.nickname || userInfo.name || '微信用户',
        level: levelInfo.level_name || '普通会员',
        growth,
        growthTarget,
        growthHint: remaining > 0 ? ('距离下一等级还差 ' + remaining) : '已达到当前等级目标'
      },
      benefits,
      levelTiers
    })
  },

  mapBenefits(source) {
    const colors = ['teal', 'amber', 'green', 'blue', 'purple', 'red']
    return (Array.isArray(source) ? source : []).map((benefit, index) => {
      const name = benefit.name || '会员权益'
      const icon = this.benefitIcon(name)
      const color = colors[index % colors.length]
      return {
        key: String(benefit.key || benefit.id || ('benefit-' + index)),
        name,
        desc: benefit.desc || '',
        icon,
        color,
        iconUrl: buildIcon(icon, this._benefitColor(color))
      }
    })
  },

  mapLevels(source, currentLevel) {
    return (Array.isArray(source) ? source : []).map(level => {
      const levelNumber = Number(level.level)
      const benefits = Array.isArray(level.benefits) ? level.benefits : []
      const perks = benefits.map(item => {
        const name = item && item.name ? item.name : ''
        const desc = item && item.desc ? item.desc : ''
        return [name, desc].filter(Boolean).join(' · ')
      }).filter(Boolean)
      const icon = levelNumber >= 3 ? 'star' : 'award'
      const color = levelNumber >= 3 ? 'blue' : (levelNumber >= 2 ? 'accent' : '#9CA3AF')
      const tierTone = levelNumber >= 3 ? 'diamond' : (levelNumber >= 2 ? 'gold' : 'silver')
      return {
        key: String(level.level),
        name: level.level_name || ('等级 ' + level.level),
        perks,
        current: Number(currentLevel) === levelNumber,
        icon,
        color,
        tierTone,
        iconUrl: buildIcon(icon, this._tierColor(color))
      }
    })
  },

  benefitIcon(name) {
    if (name.indexOf('折扣') >= 0) return 'coupon'
    if (name.indexOf('响应') >= 0) return 'clock'
    if (name.indexOf('派单') >= 0) return 'zap'
    if (name.indexOf('客服') >= 0) return 'message'
    if (name.indexOf('生日') >= 0) return 'star'
    if (name.indexOf('延保') >= 0) return 'shield'
    return 'home'
  },

  _benefitColor(color) {
    const map = { teal: COLORS.brand, amber: COLORS.accent, green: COLORS.green, blue: '#5A8FAD', purple: COLORS.accentDark, red: COLORS.danger }
    return map[color] || COLORS.brand
  },

  _tierColor(color) {
    const map = { accent: COLORS.accent, blue: '#5A8FAD' }
    return map[color] || color
  },

  onTaskTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'first') {
      wx.redirectTo({ url: '/pages/client-publish/index' })
      return
    }
    if (key === 'review') {
      wx.redirectTo({ url: '/pages/client-orders/index' })
      return
    }
    wx.showToast({ title: '该成长任务暂未开放', icon: 'none' })
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-mine/index' }) })
  }
})

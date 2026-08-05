const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    loading: true,
    loadError: false,
    signing: false,
    balance: 0,
    balanceText: '0',
    todaySignin: false,
    logs: [],
    visibleLogs: [],
    activeTab: 'all',
    icons: {}
  },

  onLoad() {
    this.setData({
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        info: buildIcon('info', COLORS.text1),
        check: buildIcon('check', COLORS.brand),
        yuan: buildIcon('yuan', COLORS.brand),
        message: buildIcon('message', COLORS.brand),
        share: buildIcon('send', COLORS.brand),
        coupon: buildIcon('coupon', COLORS.accent),
        gift: buildIcon('gift', COLORS.accent),
        mallYuan: buildIcon('yuan', COLORS.accent),
        award: buildIcon('award', COLORS.accent),
        plus: buildIcon('arrow-up', COLORS.green),
        minus: buildIcon('arrow-down', COLORS.accent)
      }
    })
    this.loadData()
  },

  onPullDownRefresh() {
    this.loadData().finally(() => wx.stopPullDownRefresh())
  },

  formatNumber(value) {
    const number = Number(value || 0)
    return Number.isFinite(number) ? number.toLocaleString('zh-CN') : '0'
  },

  formatTime(value) {
    if (!value) return ''
    const source = String(value)
    const date = new Date(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(source) ? source + 'Z' : source)
    if (Number.isNaN(date.getTime())) return ''
    const pad = n => String(n).padStart(2, '0')
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
  },

  normalizeLogs(payload) {
    const items = Array.isArray(payload) ? payload : (payload && Array.isArray(payload.items) ? payload.items : [])
    return items.map(item => {
      const change = Number(item.change || 0)
      return {
        id: item.id,
        title: item.reason || '积分变动',
        time: this.formatTime(item.created_at),
        change,
        amountText: (change > 0 ? '+' : '') + change,
        type: change >= 0 ? 'plus' : 'minus'
      }
    })
  },

  async loadData() {
    this.setData({ loading: true, loadError: false })
    try {
      const api = app.getApi()
      const results = await Promise.all([api.points.detail(), api.points.logs({ page: 1, size: 100 })])
      const detail = results[0] || {}
      const logs = this.normalizeLogs(results[1])
      this.setData({
        balance: Number(detail.balance || 0),
        balanceText: this.formatNumber(detail.balance),
        todaySignin: detail.today_signin === true,
        logs,
        loading: false
      })
      this.applyFilter()
    } catch (error) {
      console.error('加载积分失败', error)
      this.setData({ loading: false, loadError: true })
    }
  },

  applyFilter() {
    const tab = this.data.activeTab
    const logs = this.data.logs.filter(item => tab === 'all' || (tab === 'earn' ? item.change > 0 : item.change < 0))
    this.setData({ visibleLogs: logs })
  },

  onTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.key })
    this.applyFilter()
  },

  async onSignin() {
    if (this.data.todaySignin || this.data.signing) return
    this.setData({ signing: true })
    try {
      const result = await app.getApi().points.signin()
      const got = Number(result && result.got_points)
      wx.showToast({ title: got > 0 ? '签到成功 +' + got : '签到成功', icon: 'success' })
      await this.loadData()
    } catch (error) {
      console.error('积分签到失败', error)
    } finally {
      this.setData({ signing: false })
    }
  },

  onRules() {
    wx.showModal({
      title: '积分规则',
      content: '积分获取、每日上限、过期与兑换均以服务端当前规则和真实流水为准；页面不会预先写死奖励或扣减积分。',
      showCancel: false,
      confirmColor: '#0D9488'
    })
  },

  onInvite() { wx.navigateTo({ url: '/pages/client-invite/index' }) },
  onUnavailable() { wx.showToast({ title: '积分兑换尚未配置，不会扣除积分', icon: 'none' }) },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

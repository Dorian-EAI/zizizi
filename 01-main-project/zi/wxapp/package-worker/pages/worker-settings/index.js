// pages/worker-settings/index.js — 师傅设置页
const app = getApp()
const api = app.getApi()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    statusBarHeight: 20,
    notifications: [
      { key: 'new_order', label: '新订单提醒', value: null, iconClass: 'row-icon-orange', iconKey: 'bell' },
      { key: 'system', label: '系统消息', value: null, iconClass: 'row-icon-blue', iconKey: 'message' },
      { key: 'income_change', label: '收益到账提醒', value: null, iconClass: 'row-icon-brand', iconKey: 'wallet' }
    ],
    isOnline: false,
    workerProfile: {
      name: '—',
      avatar: '',
      levelText: '—',
      completedOrdersText: '—',
      praiseRateText: '—',
      serviceAreaText: '—',
      serviceTypesText: '—',
      phoneStatusText: '未绑定',
      certificationText: '未认证',
      certificationTone: '',
      certificatesText: '—'
    },
    cacheText: '—',
    aboutItems: [
      { key: 'agreement', label: '用户协议' },
      { key: 'privacy', label: '隐私政策' },
      { key: 'about', label: '关于我们' },
      { key: 'help', label: '帮助中心' }
    ],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        // 导航
        back: buildIcon('arrowLeft', COLORS.text1),
        arrow: buildIcon('arrowRight', COLORS.text3),
        // 资料卡
        user: buildIcon('user', COLORS.brandWorker),
        star: buildIcon('star', COLORS.accentDark),
        // 接单设置
        location: buildIcon('location', COLORS.brandWorker),
        grid: buildIcon('grid', '#5A8FAD'),
        power: buildIcon('power', '#5B8C5A'),
        zap: buildIcon('zap', COLORS.accent),
        // 账号与安全
        lock: buildIcon('lock', COLORS.brandWorker),
        phone: buildIcon('phone', '#5A8FAD'),
        shield: buildIcon('shield', '#5B8C5A'),
        award: buildIcon('award', COLORS.accent),
        // 消息通知
        bell: buildIcon('bell', COLORS.accent),
        wallet: buildIcon('wallet', COLORS.brandWorker),
        message: buildIcon('message', '#5A8FAD'),
        // 其他
        trash: buildIcon('trash', COLORS.accent),
        info: buildIcon('info', COLORS.brandWorker),
        orders: buildIcon('orders', '#5A8FAD'),
        // 退出
        logout: buildIcon('logout', COLORS.danger)
      }
    })
    this.loadSettings()
    this.loadProfile()
    this.loadStorageSize()
  },

  async loadSettings() {
    try {
      const res = await api.settings.getNotification()
      const notifications = this.data.notifications.map(n => {
        const v = res ? res[this._backendNotifKey(n.key)] : undefined
        return { ...n, value: v != null ? !!v : n.value }
      })
      this.setData({ notifications })
    } catch (e) {
      console.error('加载通知设置失败', e)
    }
  },

  // 前端通知 key → 后端 push_* 字段（new_order→push_order, system→push_system, income_change→push_sms）
  _backendNotifKey(key) {
    const m = { new_order: 'push_order', system: 'push_system', income_change: 'push_sms' }
    return m[key] || key
  },

  async loadProfile() {
    try {
      const me = await api.auth.workerMe()
      const certifiedMap = {
        0: { text: '未认证', tone: '' },
        1: { text: '审核中', tone: '' },
        2: { text: '已认证', tone: 'green' },
        3: { text: '未通过', tone: '' }
      }
      const certification = certifiedMap[Number(me.certified)] || certifiedMap[0]
      const certificates = Array.isArray(me.certificates)
        ? me.certificates
        : (me.certification_data && Array.isArray(me.certification_data.certificate_images)
            ? me.certification_data.certificate_images
            : null)
      const serviceTypes = Array.isArray(me.service_types) ? me.service_types.filter(Boolean) : []
      this.setData({
        isOnline: !!me.is_online,
        workerProfile: {
          name: me.real_name || me.nickname || '—',
          avatar: me.avatar || '',
          levelText: me.level != null ? ('L' + me.level) : '—',
          completedOrdersText: me.completed_orders != null ? String(me.completed_orders) : '—',
          praiseRateText: me.praise_rate != null ? (String(me.praise_rate) + '%') : '—',
          serviceAreaText: me.service_area || '—',
          serviceTypesText: serviceTypes.length ? serviceTypes.join('/') : '—',
          phoneStatusText: me.phone ? '已绑定' : '未绑定',
          certificationText: certification.text,
          certificationTone: certification.tone,
          certificatesText: certificates ? (certificates.length + ' 张') : '—'
        }
      })
    } catch (e) {
      console.error('加载师傅信息失败', e)
    }
  },

  loadStorageSize() {
    try {
      const info = wx.getStorageInfoSync()
      const currentKb = Number(info && info.currentSize)
      this.setData({ cacheText: Number.isFinite(currentKb) ? (currentKb / 1024).toFixed(2) + 'MB' : '—' })
    } catch (e) {
      this.setData({ cacheText: '—' })
    }
  },

  onCertificationTap() {
    wx.navigateTo({ url: '/package-worker/pages/worker-certification/index' })
  },

  async onToggleNotification(e) {
    const idx = e.currentTarget.dataset.idx
    const item = this.data.notifications[idx]
    if (!item || typeof item.value !== 'boolean') {
      wx.showToast({ title: '通知设置尚未加载', icon: 'none' })
      return
    }
    const newValue = !item.value
    const notifications = this.data.notifications.map((n, i) => i === idx ? { ...n, value: newValue } : n)
    this.setData({ notifications })
    try {
      await api.settings.updateNotification({ [this._backendNotifKey(item.key)]: newValue })
    } catch (e) {
      // 回滚
      const rollback = this.data.notifications.map((n, i) => i === idx ? { ...n, value: !newValue } : n)
      this.setData({ notifications: rollback })
      wx.showToast({ title: '更新失败', icon: 'none' })
    }
  },

  onToggleOnline() {
    // /api/auth/profile 仅接受用户令牌；后端尚无师傅接单状态写接口，保持服务端状态不变。
    wx.showToast({ title: '接单状态接口暂未开放', icon: 'none' })
  },

  async onAboutItem(e) {
    const key = e.currentTarget.dataset.key
    const item = this.data.aboutItems.find(i => i.key === key)
    if (!item) return
    wx.showLoading({ title: '加载中', mask: true })
    try {
      const page = await api.pages.byKey(key)
      const content = page && typeof page.content === 'string' ? page.content.trim() : ''
      if (!content) throw new Error('内容暂未配置')
      wx.hideLoading()
      wx.showModal({
        title: page.title || item.label,
        content,
        showCancel: false,
        confirmColor: '#2D6CDF'
      })
    } catch (e) {
      wx.hideLoading()
      console.error('加载内容页失败', e)
      wx.showToast({ title: (e && e.message) || '内容加载失败', icon: 'none' })
    }
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出当前账号吗？',
      confirmColor: '#DC2626',
      success: async (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '退出中...' })
        try {
          await api.auth.logout()
        } catch (e) {
          // 忽略后端错误，仍执行本地清理
        }
        app.clearLogin()
        wx.hideLoading()
        wx.reLaunch({ url: '/pages/entry/index' })
      }
    })
  },

  onBack() {
    wx.navigateBack()
  }
})

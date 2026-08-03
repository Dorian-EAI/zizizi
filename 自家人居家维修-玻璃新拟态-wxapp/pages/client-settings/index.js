// pages/client-settings/index.js — 设置 玻璃新拟态
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { DEV_STORAGE_KEYS } = require('../../config/env')

Page({
  data: {
    statusBarHeight: 20,
    accountInfo: {
      name: '',
      phone: ''
    },
    notifications: [
      { key: 'order',   name: '订单通知', desc: '订单状态变更提醒', value: null, color: 'orange', icon: 'bell' },
      { key: 'coupon',  name: '优惠提醒', desc: '优惠券与活动提醒', value: null, color: 'brand',  icon: 'coupon' },
      { key: 'service', name: '系统消息', desc: '系统消息通知',     value: null, color: 'blue',   icon: 'message' }
    ],
    securityItems: [
      { key: 'loginSecurity', name: '登录与安全', color: 'brand', icon: 'lock', valueText: '微信登录', badge: '' },
      { key: 'bindPhone', name: '绑定手机', color: 'blue', icon: 'phone', valueText: '' },
      { key: 'realname', name: '实名认证', color: 'green', icon: 'shield', valueText: '仅师傅端', badge: '' }
    ],
    privacyItems: [
      { key: 'privacySetting', name: '隐私设置', color: 'blue',   icon: 'shield' },
      { key: 'authMgmt',       name: '授权管理', color: 'orange', icon: 'lock' }
    ],
    aboutItems: [
      { key: 'cache',     name: '清除缓存', color: 'orange', icon: 'refresh', valueText: '—' },
      { key: 'about',     name: '关于我们', color: 'brand',  icon: 'star' },
      { key: 'agreement', name: '用户协议', color: 'blue',   icon: 'list' },
      { key: 'privacy',   name: '隐私政策', color: 'green',  icon: 'lock' }
    ],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        account: buildIcon('user', COLORS.brand),
        arrowRight: buildIcon('arrowRight', COLORS.text3)
      }
    })
    // 给各项附加图标 URI
    const colorMap = {
      brand: COLORS.brand,
      green: COLORS.green,
      blue: COLORS.blue,
      orange: COLORS.orange
    }
    const aboutItems = this.data.aboutItems.map(it => Object.assign({}, it, {
      iconUrl: buildIcon(it.icon, colorMap[it.color] || COLORS.brand)
    }))
    const securityItems = this.data.securityItems.map(it => Object.assign({}, it, {
      iconUrl: buildIcon(it.icon, colorMap[it.color] || COLORS.brand)
    }))
    const privacyItems = this.data.privacyItems.map(it => Object.assign({}, it, {
      iconUrl: buildIcon(it.icon, colorMap[it.color] || COLORS.brand)
    }))
    const notifications = this.data.notifications.map(it => Object.assign({}, it, {
      iconUrl: buildIcon(it.icon, colorMap[it.color] || COLORS.brand)
    }))
    this.setData({ aboutItems, securityItems, privacyItems, notifications })
    this.loadAccountInfo()
    this.loadNotification()
    this.refreshCacheSize()
  },

  // 加载账号信息
  async loadAccountInfo() {
    let userInfo = null
    try {
      const response = await app.getApi().auth.me()
      const remote = response && response.user ? response.user : response
      if (remote && typeof remote === 'object') {
        userInfo = remote
        this.syncUserCache(userInfo)
      }
    } catch (e) {
      console.error('读取服务端账号信息失败，使用本地缓存', e)
    }
    if (!userInfo) {
      try {
        userInfo = app.globalData.userInfo || wx.getStorageSync('userInfo') || {}
      } catch (e) {
        userInfo = {}
      }
    }
    this.applyAccountInfo(userInfo)
    return userInfo
  },

  syncUserCache(userInfo) {
    app.globalData.userInfo = userInfo
    try { wx.setStorageSync('userInfo', userInfo) } catch (e) {}
  },

  applyAccountInfo(userInfo) {
    const info = userInfo || {}
    const hasPhone = /^1[3-9]\d{9}$/.test(String(info.phone || ''))
    const securityItems = this.data.securityItems.map(item => {
      if (item.key === 'bindPhone') {
        return Object.assign({}, item, { valueText: hasPhone ? '已绑定' : '未绑定' })
      }
      if (item.key === 'realname') {
        return Object.assign({}, item, { valueText: '仅师傅端', badge: '' })
      }
      return item
    })
    this.setData({
      accountInfo: {
        name: info.nickname || info.name || '未设置',
        phone: hasPhone ? this.maskPhone(info.phone) : '—'
      },
      securityItems
    })
  },

  maskPhone(phone) {
    if (!phone || phone.length < 7) return phone
    return phone.slice(0, 3) + '****' + phone.slice(-4)
  },

  async loadNotification() {
    const api = app.getApi()
    try {
      const res = await api.settings.getNotification()
      const map = res || {}
      const notifications = this.data.notifications.map(n => {
        const value = map[this._backendNotifKey(n.key)]
        return Object.assign({}, n, {
          value: typeof value === 'boolean' ? value : null
        })
      })
      this.setData({ notifications })
    } catch (e) {
      console.error('加载通知设置失败', e)
    }
  },

  // 前端通知 key → 后端 push_* 字段（order→push_order, coupon→push_activity, service→push_system）
  _backendNotifKey(key) {
    const m = { order: 'push_order', coupon: 'push_activity', service: 'push_system' }
    return m[key] || key
  },

  // 切换通知开关（自定义 toggle：bindtap 触发，从 data 读取当前值并取反）
  onSwitchChange(e) {
    const key = e.currentTarget.dataset.key
    const current = this.data.notifications.find(n => n.key === key)
    if (!current) return
    if (typeof current.value !== 'boolean') {
      wx.showToast({ title: '通知设置尚未加载', icon: 'none' })
      return
    }
    const value = !current.value
    const notifications = this.data.notifications.map(n => n.key === key ? Object.assign({}, n, { value }) : n)
    this.setData({ notifications })
    const api = app.getApi()
    api.settings.updateNotification({ [this._backendNotifKey(key)]: value }).catch(err => {
      console.error('更新通知设置失败', err)
      wx.showToast({ title: '设置失败', icon: 'none' })
      // 回滚
      const rolled = this.data.notifications.map(n => n.key === key ? Object.assign({}, n, { value: !value }) : n)
      this.setData({ notifications: rolled })
    })
  },

  // 编辑资料
  async onEditProfile() {
    const oldName = this.data.accountInfo.name === '未设置' ? '' : this.data.accountInfo.name
    const nickname = await this.promptInput('编辑昵称', '请输入昵称', oldName)
    if (!nickname || nickname === oldName) return
    if (nickname.length > 32) {
      wx.showToast({ title: '昵称不能超过32个字符', icon: 'none' })
      return
    }
    wx.showLoading({ title: '保存中', mask: true })
    try {
      const response = await app.getApi().auth.updateProfile({ nickname })
      const userInfo = response && response.user ? response.user : response
      if (!userInfo || typeof userInfo !== 'object') throw new Error('更新资料响应无效')
      this.syncUserCache(userInfo)
      this.applyAccountInfo(userInfo)
      wx.hideLoading()
      wx.showToast({ title: '资料已更新', icon: 'success' })
    } catch (error) {
      wx.hideLoading()
      console.error('更新用户资料失败', error)
    }
  },

  // 隐私组点击
  onPrivacyTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'privacySetting') {
      this.showContentPage('privacy')
      return
    }
    if (key === 'authMgmt') {
      if (typeof wx.openSetting !== 'function') {
        wx.showToast({ title: '当前微信版本不支持授权管理', icon: 'none' })
        return
      }
      wx.openSetting({
        fail: error => {
          console.error('打开授权管理失败', error)
          wx.showToast({ title: '无法打开授权管理', icon: 'none' })
        }
      })
    }
  },

  // 关于卡：协议 / 隐私 / 关于
  onAboutTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'cache') {
      this.onClearCache()
      return
    }
    if (key === 'agreement' || key === 'privacy' || key === 'about') {
      this.showContentPage(key)
    }
  },

  async showContentPage(key) {
    const titles = { agreement: '用户协议', privacy: '隐私政策', about: '关于我们' }
    const api = app.getApi()
    const loader = api.pages && (api.pages[key] || api.pages.byKey)
    if (typeof loader !== 'function') {
      wx.showToast({ title: '内容服务不可用', icon: 'none' })
      return
    }
    wx.showLoading({ title: '加载中', mask: true })
    try {
      const page = api.pages[key] ? await api.pages[key]() : await api.pages.byKey(key)
      wx.hideLoading()
      const content = this.plainTextContent(page && page.content)
      if (!content) {
        wx.showToast({ title: '暂无相关内容', icon: 'none' })
        return
      }
      const maxLength = 1800
      const displayed = content.length > maxLength
        ? content.slice(0, maxLength) + '\n\n（内容较长，当前展示前1800字）'
        : content
      wx.showModal({
        title: (page && page.title) || titles[key],
        content: displayed,
        showCancel: false,
        confirmColor: '#0D9488'
      })
    } catch (error) {
      wx.hideLoading()
      console.error('加载内容页失败', error)
    }
  },

  plainTextContent(content) {
    return String(content || '')
      .replace(/^#{1,6}\s*/gm, '')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\[(.*?)\]\([^)]*\)/g, '$1')
      .replace(/^[-*]\s+/gm, '• ')
      .replace(/^---+\s*$/gm, '')
      .trim()
  },

  // 安全卡：修改密码 / 绑定手机 / 实名认证
  onSecurityTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'loginSecurity') {
      wx.showModal({
        title: '登录与安全',
        content: '当前账号通过微信授权登录，不设置独立密码。请妥善保护微信账号；如发现异常，可退出后重新授权登录。',
        showCancel: false,
        confirmColor: '#0D9488'
      })
    } else if (key === 'bindPhone') {
      this.onBindPhone()
    } else if (key === 'realname') {
      wx.showModal({
        title: '实名认证',
        content: '普通用户无需实名认证。实名认证与资质审核仅面向接单师傅，请切换到师傅端后提交认证资料。',
        showCancel: false,
        confirmColor: '#0D9488'
      })
    }
  },

  promptInput(title, placeholderText, initialValue) {
    return new Promise(resolve => {
      wx.showModal({
        title,
        editable: true,
        content: initialValue || '',
        placeholderText,
        confirmColor: '#0D9488',
        success: result => resolve(result.confirm ? String(result.content || '').trim() : '')
      })
    })
  },

  async onBindPhone() {
    const phone = await this.promptInput('绑定手机', '请输入11位手机号')
    if (!phone) return
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      wx.showToast({ title: '手机号格式不正确', icon: 'none' })
      return
    }

    const api = app.getApi()
    wx.showLoading({ title: '发送验证码', mask: true })
    try {
      const sendResult = await api.sms.sendCode(phone)
      wx.hideLoading()
      const canShowDevelopmentCode = app.globalData.envVersion === 'develop' &&
        app.globalData.useMock === true && sendResult && sendResult.code
      if (canShowDevelopmentCode) {
        await new Promise(resolve => {
          wx.showModal({
            title: '开发环境验证码',
            content: '后端返回的本地联调验证码：' + String(sendResult.code),
            showCancel: false,
            confirmColor: '#0D9488',
            success: resolve,
            fail: resolve
          })
        })
      }
      const code = await this.promptInput('输入验证码', '请输入短信验证码')
      if (!code) return
      if (!/^\d{4,8}$/.test(code)) {
        wx.showToast({ title: '验证码格式不正确', icon: 'none' })
        return
      }

      wx.showLoading({ title: '绑定中', mask: true })
      const userInfo = await api.auth.bindPhone(phone, code)
      const account = userInfo && userInfo.user ? userInfo.user : userInfo
      this.syncUserCache(account)
      this.applyAccountInfo(account)
      wx.hideLoading()
      wx.showToast({ title: '绑定成功', icon: 'success' })
    } catch (error) {
      wx.hideLoading()
      console.error('绑定手机号失败', error)
    }
  },

  refreshCacheSize() {
    let valueText = '—'
    try {
      const info = wx.getStorageInfoSync()
      valueText = this.formatStorageSize(info && info.currentSize)
    } catch (error) {
      console.error('读取缓存大小失败', error)
    }
    const aboutItems = this.data.aboutItems.map(item => item.key === 'cache'
      ? Object.assign({}, item, { valueText })
      : item)
    this.setData({ aboutItems })
  },

  formatStorageSize(sizeInKB) {
    const size = Number(sizeInKB)
    if (!Number.isFinite(size) || size <= 0) return '0KB'
    if (size < 1024) return Math.round(size) + 'KB'
    const mb = size / 1024
    return (mb >= 10 ? mb.toFixed(0) : mb.toFixed(1)) + 'MB'
  },

  onClearCache() {
    wx.showModal({
      title: '清除缓存',
      content: '确定清除本地非登录缓存吗？当前登录状态和开发环境配置将保留。',
      confirmColor: '#0D9488',
      success: (res) => {
        if (!res.confirm) return
        try {
          // 保留登录态与角色
          const token = wx.getStorageSync('token')
          const userInfo = wx.getStorageSync('userInfo')
          const role = wx.getStorageSync('role')
          const devBaseURL = wx.getStorageSync(DEV_STORAGE_KEYS.BASE_URL)
          const devUseMock = wx.getStorageSync(DEV_STORAGE_KEYS.USE_MOCK)
          wx.clearStorageSync()
          if (token) wx.setStorageSync('token', token)
          if (userInfo) wx.setStorageSync('userInfo', userInfo)
          if (role) wx.setStorageSync('role', role)
          if (devBaseURL) wx.setStorageSync(DEV_STORAGE_KEYS.BASE_URL, devBaseURL)
          if (devUseMock === true || devUseMock === 'true') {
            wx.setStorageSync(DEV_STORAGE_KEYS.USE_MOCK, devUseMock)
          }
          wx.showToast({ title: '已清除缓存', icon: 'success' })
          this.refreshCacheSize()
        } catch (e) {
          wx.showToast({ title: '清除失败', icon: 'none' })
        }
      }
    })
  },

  // 退出登录
  onLogoutTap() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出当前账号吗？',
      confirmText: '退出',
      confirmColor: '#DC2626',
      success: async (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '退出中', mask: true })
        try {
          const api = app.getApi()
          try { await api.auth.logout() } catch (e) { /* 忽略网络失败 */ }
          app.clearLogin()
          wx.hideLoading()
          wx.reLaunch({ url: '/pages/entry/index' })
        } catch (e) {
          wx.hideLoading()
          wx.showToast({ title: '退出失败', icon: 'none' })
        }
      }
    })
  },

  onBack() {
    wx.navigateBack({ delta: 1, fail: () => wx.redirectTo({ url: '/pages/client-mine/index' }) })
  }
})

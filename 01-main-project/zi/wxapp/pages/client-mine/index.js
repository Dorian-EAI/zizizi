// pages/client-mine/index.js — 客户端个人中心（设计画布更新）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const MENU_TONES_BY_KEY = {
  member: 'blue',
  address: 'purple',
  coupon: 'amber',
  wallet: 'teal',
  favorites: 'red',
  invoice: 'green',
  notifications: 'red',
  security: 'green',
  privacy: 'gray',
  service: 'cyan',
  feedback: 'slate',
  settings: 'blue',
  about: 'blue'
}

const MENU_TONE_COLORS = {
  amber: COLORS.orange,
  blue: COLORS.blue,
  cyan: COLORS.blue,
  gray: COLORS.text2,
  green: COLORS.green,
  purple: '#5856D6',
  red: COLORS.red,
  slate: COLORS.text2,
  teal: COLORS.brand
}

function decorateMenuSections(sections) {
  return sections.map(section => ({
    id: section.id,
    items: section.items.map(item => {
      const tone = item.tone || MENU_TONES_BY_KEY[item.key] || 'teal'
      return Object.assign({}, item, {
        tone,
        iconUrl: buildIcon(item.icon, MENU_TONE_COLORS[tone] || COLORS.brand)
      })
    })
  }))
}

Page({
  data: {
    statusBarHeight: 20,
    userInfo: {
      name: '微信用户',
      phone: '未绑定',
      avatarUrl: '',
      level: '普通会员',
      verified: false,
      stats: { orders: 0, reviews: 0, favorites: 0 }
    },
    menuSections: [
      {
        id: 'service',
        items: [
          { key: 'member',    label: '会员中心',   icon: 'award',    color: '#0D9488', route: '/package-client/pages/client-member/index' },
          { key: 'address',   label: '我的地址',   icon: 'location', color: '#5A8FAD', route: '/pages/address/index' },
          { key: 'coupon',    label: '优惠券',     icon: 'coupon',   color: '#D4944C', route: '/package-client/pages/client-coupon/index', badge: '' },
          { key: 'wallet',    label: '我的钱包',   icon: 'wallet',   color: '#D4944C', route: '', badge: '' },
          { key: 'favorites', label: '收藏的师傅', icon: 'heart',    color: '#C4533A', route: '/package-client/pages/client-favorite-workers/index' },
          { key: 'invoice',   label: '发票与报销', icon: 'orders',   color: '#0D9488', route: '' }
        ]
      },
      {
        id: 'settings',
        items: [
          { key: 'notifications', label: '消息通知',   icon: 'bell',         color: '#C4533A', route: '', badge: '' },
          { key: 'security',      label: '账号安全',   icon: 'shield',       color: '#5B8C5A', route: '' },
          { key: 'privacy',       label: '隐私设置',   icon: 'eye',          color: '#8B8178', route: '' },
          { key: 'service',       label: '客服中心',   icon: 'phone',        color: '#5A8FAD', route: '/package-client/pages/client-service/index' },
          { key: 'feedback',      label: '意见反馈',   icon: 'message',      color: '#0D9488', route: '/package-client/pages/client-feedback/index' },
          { key: 'settings',      label: '设置',       icon: 'settings',     color: '#8B8178', route: '/pages/client-settings/index' },
          { key: 'about',         label: '关于我们',   icon: 'star',         color: '#5A8FAD', route: '', badge: '' }
        ]
      }
    ],
    icons: {}
  },

  onLoad() {
    const icons = {
      edit: buildIcon('edit', '#FFFFFF'),
      refresh: buildIcon('refresh', COLORS.brand),
      chevron: buildIcon('arrowRight', COLORS.text2),
      award: buildIcon('award', COLORS.white),
      location: buildIcon('location', COLORS.white),
      coupon: buildIcon('coupon', COLORS.white),
      wallet: buildIcon('wallet', COLORS.white),
      heart: buildIcon('heart', COLORS.white),
      orders: buildIcon('orders', COLORS.white),
      bell: buildIcon('bell', COLORS.white),
      shield: buildIcon('shield', COLORS.white),
      eye: buildIcon('eye', COLORS.white),
      phone: buildIcon('phone', COLORS.white),
      message: buildIcon('message', COLORS.white),
      settings: buildIcon('settings', COLORS.white),
      star: buildIcon('star', COLORS.white)
    }
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons,
      menuSections: decorateMenuSections(this.data.menuSections)
    })
    this.loadUserInfo()
  },

  onShow() {
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
  },

  async loadUserInfo() {
    const api = app.getApi()
    try {
      const info = await api.getUserInfo()
      // 后端 /api/auth/me 返回 snake_case: nickname / member_level / avatar
      // 前端 WXML 绑定 name / level / avatarUrl，需做字段映射兜底
      const merged = Object.assign({}, this.data.userInfo, info, {
        name: info.nickname != null ? info.nickname : (this.data.userInfo.name || '用户'),
        phone: info.phone || '未绑定',
        level: info.member_level != null ? ('Lv.' + info.member_level) : this.data.userInfo.level,
        verified: !!info.phone,
        avatarUrl: info.avatar ? info.avatar : buildIcon('user', COLORS.brand),
        stats: Object.assign({ orders: 0, reviews: 0, favorites: 0 }, info.summary || {})
      })
      const summary = info.summary || {}
      let version = ''
      try {
        const account = wx.getAccountInfoSync && wx.getAccountInfoSync()
        version = account && account.miniProgram && account.miniProgram.version
          ? ('v' + account.miniProgram.version)
          : ''
      } catch (e) {}
      const menuSections = this.data.menuSections.map(section => ({
        id: section.id,
        items: section.items.map(item => {
          let badge = item.badge || ''
          if (item.key === 'coupon') badge = summary.available_coupons ? (summary.available_coupons + ' 张') : ''
          if (item.key === 'wallet') badge = info.balance != null ? ('¥' + Number(info.balance).toFixed(2)) : ''
          if (item.key === 'notifications') badge = summary.unread_messages ? (summary.unread_messages + ' 条未读') : ''
          if (item.key === 'about') badge = version
          return Object.assign({}, item, { badge })
        })
      }))
      app.globalData.userInfo = info
      try { wx.setStorageSync('userInfo', info) } catch (e) {}
      this.setData({ userInfo: merged, menuSections })
    } catch (e) {
      this.setData({
        'userInfo.avatarUrl': buildIcon('user', COLORS.brand)
      })
      console.error('加载用户信息失败', e)
    }
  },

  onEditTap() {
    wx.showToast({ title: '编辑资料', icon: 'none' })
  },

  onMenuTap(e) {
    const key = e.currentTarget.dataset.key
    const routes = {}
    // 从 menuSections 构建路由映射
    this.data.menuSections.forEach(section => {
      section.items.forEach(item => {
        routes[item.key] = item.route
      })
    })
    const url = routes[key]
    if (url) {
      wx.navigateTo({ url })
    } else {
      wx.showToast({ title: '功能开发中', icon: 'none' })
    }
  },

  onSwitchRole() {
    wx.showModal({
      title: '切换身份',
      content: '是否切换到师傅端？',
      confirmColor: '#0D9488',
      success: (res) => {
        if (res.confirm) {
          // 用户与师傅使用不同类型的访问令牌，切端前必须重新完成对应身份登录。
          app.clearLogin()
          app.setRole('')
          wx.reLaunch({ url: '/pages/entry/index?reason=switch-role' })
        }
      }
    })
  }
})

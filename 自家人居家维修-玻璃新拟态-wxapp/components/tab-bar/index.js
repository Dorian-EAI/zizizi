// components/tab-bar/index.js
// 玻璃新拟态 浮动胶囊 tabBar
// 双端共用：根据 globalData.role 渲染不同 tab 集合
// 激活态使用新拟态凹陷（inset），非激活态为玻璃底

const { buildIcon } = require('../../utils/icons')

// 双端 tab 定义
const TAB_SETS = {
  client: [
    { key: 'home',    text: '首页', icon: 'home',   path: '/pages/client-home/index' },
    { key: 'publish', text: '发布', icon: 'plus',   path: '/pages/client-publish/index', elevated: true },
    { key: 'orders',  text: '订单', icon: 'orders', path: '/pages/client-orders/index' },
    { key: 'mine',    text: '我的', icon: 'user',   path: '/pages/client-mine/index' }
  ],
  worker: [
    { key: 'hall',    text: '接单', icon: 'hall',   path: '/pages/worker-home/index' },
    { key: 'orders',  text: '订单', icon: 'orders', path: '/pages/worker-orders/index' },
    { key: 'wallet',  text: '钱包', icon: 'wallet', path: '/pages/worker-wallet/index' },
    { key: 'mine',    text: '我的', icon: 'user',   path: '/pages/worker-profile/index' }
  ]
}

Component({
  options: { multipleSlots: true },

  properties: {
    active: { type: String, value: '' }
  },

  data: {
    role: 'client',
    tabs: [],
    primaryColor: '#0D9488'
  },

  lifetimes: {
    attached() {
      const app = getApp()
      const role = app.globalData.role || 'client'
      const primaryColor = role === 'worker' ? '#2D6CDF' : '#0D9488'
      this.applyTabs(role, primaryColor)
    }
  },

  methods: {
    applyTabs(role, primaryColor) {
      const tabs = (TAB_SETS[role] || TAB_SETS.client).map(tab => {
        return Object.assign({}, tab, {
          iconSrc: buildIcon(tab.icon, '#8B8178'),
          iconActive: buildIcon(tab.icon, primaryColor),
          iconActiveLight: buildIcon(tab.icon, '#FFFFFF')
        })
      })
      this.setData({ role, tabs, primaryColor })
    },

    onTap(e) {
      const { key, path } = e.currentTarget.dataset
      if (key === this.data.active) return
      wx.redirectTo({ url: path })
    },

    refresh() {
      const app = getApp()
      const role = app.globalData.role || 'client'
      const primaryColor = role === 'worker' ? '#2D6CDF' : '#0D9488'
      this.applyTabs(role, primaryColor)
    }
  }
})

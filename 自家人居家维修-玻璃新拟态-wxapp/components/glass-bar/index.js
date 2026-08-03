// components/glass-bar/index.js
// 玻璃新拟态 顶部导航栏
// 支持：透明（hero页）/ 玻璃质感（详情页）
// 自动适配状态栏高度
Component({
  options: { multipleSlots: true },

  properties: {
    // 标题
    title: { type: String, value: '' },
    // 主题：client / worker
    theme: { type: String, value: 'client' },
    // 透明模式（hero 页使用，无背景）
    transparent: { type: Boolean, value: false },
    // 是否显示返回按钮
    showBack: { type: Boolean, value: true },
    // 标题颜色（透明模式下用 dark/light）
    titleColor: { type: String, value: '' }
  },

  data: {
    statusBarHeight: 20,
    navBarHeight: 44
  },

  lifetimes: {
    attached() {
      const app = getApp()
      this.setData({
        statusBarHeight: app.globalData.statusBarHeight || 20
      })
    }
  },

  methods: {
    onBack() {
      const pages = getCurrentPages()
      if (pages.length > 1) {
        wx.navigateBack({ delta: 1 })
      } else {
        const app = getApp()
        const home = app.globalData.role === 'worker'
          ? '/pages/worker-home/index'
          : '/pages/client-home/index'
        wx.redirectTo({
          url: home,
          fail: () => wx.reLaunch({ url: '/pages/entry/index' })
        })
      }
    }
  }
})

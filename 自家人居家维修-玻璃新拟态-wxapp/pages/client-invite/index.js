const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    featureAvailable: false,
    icons: {}
  },

  onLoad() {
    this.setData({
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        records: buildIcon('list', COLORS.text1),
        gift: buildIcon('gift', COLORS.white),
        user: buildIcon('user', COLORS.white),
        wechat: buildIcon('wechat', COLORS.brand),
        moments: buildIcon('image', COLORS.accentDark),
        qq: buildIcon('message', COLORS.accentDark),
        link: buildIcon('send', COLORS.brand)
      }
    })
  },

  onBack() { wx.navigateBack({ delta: 1 }) },
  onUnavailable() {
    wx.showToast({ title: '邀请关系与奖励接口尚未开放', icon: 'none' })
  },
  onRecords() {
    wx.showToast({ title: '暂无可查询的真实邀请记录', icon: 'none' })
  }
})

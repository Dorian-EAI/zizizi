const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: {
    icons: {
      gift: buildIcon('gift', COLORS.brand),
      heart: buildIcon('heart', COLORS.accentDark),
      shield: buildIcon('shield', COLORS.green)
    }
  },

  onBack() { wx.navigateBack({ delta: 1 }) },
  onMall() { wx.redirectTo({ url: '/pages/client-points-mall/index' }) },
  onPoints() { wx.navigateTo({ url: '/pages/client-points-detail/index' }) }
})

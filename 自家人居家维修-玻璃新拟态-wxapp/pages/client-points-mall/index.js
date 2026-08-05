const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

Page({
  data: { loading: true, balanceText: '—', balanceLabel: '加载中', icons: {} },
  onLoad() {
    this.setData({
      icons: {
        coupon: buildIcon('coupon', COLORS.brand),
        gift: buildIcon('gift', COLORS.accent),
        orders: buildIcon('orders', COLORS.brand),
        wallet: buildIcon('wallet', COLORS.accentDark)
      }
    })
    this.loadBalance()
  },
  async loadBalance() {
    try {
      const detail = await app.getApi().points.detail()
      const balanceText = Number(detail && detail.balance || 0).toLocaleString('zh-CN')
      this.setData({ balanceText, balanceLabel: balanceText + ' 分', loading: false })
    } catch (error) {
      console.warn('加载积分余额失败', error)
      this.setData({ balanceText: '—', balanceLabel: '积分不可用', loading: false })
    }
  },
  onPoints() { wx.navigateTo({ url: '/pages/client-points-detail/index' }) },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

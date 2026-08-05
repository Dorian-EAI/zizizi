const app = getApp()

Page({
  data: { loading: true, loadError: '', balanceText: '0', todaySignin: false, signing: false },

  onLoad() { this.loadData() },
  onShow() { if (!this.data.loading) this.loadData() },

  async loadData() {
    this.setData({ loading: true, loadError: '' })
    try {
      const detail = await app.getApi().points.detail()
      this.setData({
        balanceText: Number(detail && detail.balance || 0).toLocaleString('zh-CN'),
        todaySignin: detail && detail.today_signin === true,
        loading: false
      })
    } catch (error) {
      this.setData({ loading: false, loadError: (error && error.message) || '积分状态加载失败' })
    }
  },

  async onSignin() {
    if (this.data.todaySignin || this.data.signing) return
    this.setData({ signing: true })
    try {
      const result = await app.getApi().points.signin()
      const got = Number(result && result.got_points || 0)
      wx.showToast({ title: got > 0 ? ('签到成功 +' + got) : '签到成功', icon: 'success' })
      await this.loadData()
    } catch (error) {
      wx.showToast({ title: (error && error.message) || '签到失败', icon: 'none' })
    } finally {
      this.setData({ signing: false })
    }
  },

  onRoute(e) {
    const route = String(e.currentTarget.dataset.route || '')
    if (/^\/pages\/[a-z0-9-]+\/index(?:\?.*)?$/.test(route)) wx.navigateTo({ url: route })
  },
  onRules() {
    wx.showModal({ title: '积分任务说明', content: '除每日签到外，当前没有可查询的任务清单接口。订单、评价、邀请等是否奖励及奖励数值，以服务端实际积分流水为准。', showCancel: false })
  },
  onRetry() { this.loadData() },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

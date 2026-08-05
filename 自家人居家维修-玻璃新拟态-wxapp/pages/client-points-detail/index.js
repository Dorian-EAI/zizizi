const app = getApp()

function parseServerTime(value) {
  const source = String(value || '')
  const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(source) ? source + 'Z' : source
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatTime(value) {
  const date = parseServerTime(value)
  if (!date) return ''
  const pad = number => String(number).padStart(2, '0')
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
}

Page({
  data: {
    loading: true,
    loadError: '',
    signing: false,
    balanceText: '0',
    todaySignin: false,
    logs: [],
    visibleLogs: [],
    activeTab: 'all'
  },

  onLoad() { this.loadData() },
  onPullDownRefresh() { this.loadData().finally(() => wx.stopPullDownRefresh()) },

  async loadData() {
    this.setData({ loading: true, loadError: '' })
    try {
      const api = app.getApi()
      const results = await Promise.all([api.points.detail(), api.points.logs({ page: 1, size: 100 })])
      const detail = results[0] || {}
      const source = Array.isArray(results[1]) ? results[1] : (results[1] && results[1].items || [])
      const logs = source.map(item => {
        const change = Number(item.change || 0)
        return {
          id: item.id,
          title: item.reason || '积分变动',
          orderNo: item.order_no || '',
          timeText: formatTime(item.created_at),
          subtitle: (item.order_no ? ('订单 ' + item.order_no + ' · ') : '') + formatTime(item.created_at),
          amountText: (change > 0 ? '+' : '') + change,
          type: change >= 0 ? 'income' : 'expense',
          change,
          balanceText: item.balance_after != null ? String(item.balance_after) : ''
        }
      })
      this.setData({
        balanceText: Number(detail.balance || 0).toLocaleString('zh-CN'),
        todaySignin: detail.today_signin === true,
        logs,
        loading: false
      })
      this.applyFilter()
    } catch (error) {
      console.error('加载积分明细失败', error)
      this.setData({ loading: false, loadError: (error && error.message) || '积分明细加载失败' })
    }
  },

  applyFilter() {
    const tab = this.data.activeTab
    this.setData({
      visibleLogs: this.data.logs.filter(item => tab === 'all' || item.type === tab)
    })
  },

  onTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab })
    this.applyFilter()
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

  onTasks() { wx.navigateTo({ url: '/pages/client-points-tasks/index' }) },
  onMall() { wx.navigateTo({ url: '/pages/client-points-mall/index' }) },
  onRetry() { this.loadData() },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

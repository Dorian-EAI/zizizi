const api = require('../../../utils/request')

const TABS = [
  { key: 'unused', label: '未使用' },
  { key: 'used', label: '已使用' },
  { key: 'expired', label: '已过期' }
]

Page({
  data: {
    tabs: TABS,
    activeTab: 'unused',
    coupons: [],
    page: 1,
    size: 20,
    hasMore: true,
    loading: false
  },
  onLoad() {
    this.loadCoupons(true)
  },
  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key }, () => {
      this.loadCoupons(true)
    })
  },
  loadCoupons(reset = false) {
    if (this.data.loading) return
    if (!reset && !this.data.hasMore) return
    this.setData({ loading: true })
    const page = reset ? 1 : this.data.page
    const params = { status: this.data.activeTab, page, size: this.data.size }
    api.get('/api/coupons', params).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      this.setData({
        coupons: reset ? list : this.data.coupons.concat(list),
        page: page + 1,
        hasMore: list.length === this.data.size,
        loading: false
      })
    }).catch(() => {
      this.setData({ loading: false })
    })
  },
  onPullDownRefresh() {
    this.loadCoupons(true)
    wx.stopPullDownRefresh()
  },
  onReachBottom() {
    this.loadCoupons()
  },
  useCoupon(e) {
    const { status } = e.currentTarget.dataset
    if (status !== 'unused') return
    wx.switchTab({ url: '/pages/index/index' })
  }
})

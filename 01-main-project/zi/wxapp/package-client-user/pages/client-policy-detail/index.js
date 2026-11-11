const app = getApp()

function formatCents(value) {
  const amount = Number(value || 0) / 100
  return amount.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function formatDate(value) {
  const source = String(value || '')
  const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(source) ? source + 'Z' : source
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = number => String(number).padStart(2, '0')
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate())
}

Page({
  data: { orderId: '', orderNo: '', policy: null, loading: true, loadError: '', empty: false },

  onLoad(query) {
    this.setData({
      orderId: String(query && (query.orderId || query.id) || ''),
      orderNo: String(query && query.orderNo || '')
    })
    this.loadPolicy()
  },

  async loadPolicy() {
    if (!/^\d+$/.test(this.data.orderId)) {
      this.setData({ loading: false, loadError: '缺少有效订单标识' })
      return
    }
    this.setData({ loading: true, loadError: '', empty: false })
    try {
      const policy = await app.getApi().insurance.policy(this.data.orderId)
      if (!policy) {
        this.setData({ policy: null, loading: false, empty: true })
        return
      }
      const statusMap = { active: '保障中', claimed: '理赔处理中', expired: '已过期', cancelled: '已失效' }
      const levelMap = { basic: '基础保障', standard: '标准保障', premium: '尊享保障' }
      this.setData({
        policy: Object.assign({}, policy, {
          policyNoText: policy.policy_no || ('POL-' + policy.id),
          levelText: levelMap[policy.level] || policy.level || '安心保',
          statusText: statusMap[policy.status] || policy.status || '状态未知',
          coverageText: formatCents(policy.coverage),
          premiumText: formatCents(policy.premium),
          claimedText: formatCents(policy.claimed_amount),
          startDateText: formatDate(policy.created_at),
          endDateText: formatDate(policy.expired_at),
          orderText: this.data.orderNo || String(policy.order_id || this.data.orderId)
        }),
        canClaim: policy.status === 'active',
        loading: false
      })
    } catch (error) {
      console.error('加载保单详情失败', error)
      this.setData({ loading: false, loadError: (error && error.message) || '保单加载失败' })
    }
  },

  onClaim() {
    if (!this.data.policy || !this.data.policy.id || !this.data.canClaim) {
      wx.showToast({ title: '当前保单状态不可申请理赔', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: '/package-client/pages/client-insurance-claim/index?orderId=' + encodeURIComponent(this.data.orderId) +
        '&orderNo=' + encodeURIComponent(this.data.policy.orderText)
    })
  },
  onElectronicPolicy() {
    wx.showToast({ title: '电子保单文件接口尚未开放', icon: 'none' })
  },
  onRetry() { this.loadPolicy() },
  onBack() { wx.navigateBack({ delta: 1 }) }
})

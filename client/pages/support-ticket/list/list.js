const api = require('../../../utils/request')

const TABS = [
  { key: 'active', label: '进行中' },
  { key: 'resolved', label: '已解决' },
  { key: '', label: '全部' }
]

const STATUS_MAP = {
  pending: '待处理',
  processing: '处理中',
  resolved: '已解决',
  closed: '已关闭'
}

const PRIORITY_MAP = {
  low: '低',
  medium: '中',
  high: '高'
}

Page({
  data: {
    tabs: TABS,
    activeTab: 'active',
    tickets: [],
    page: 1,
    size: 20,
    hasMore: true,
    loading: false,
    formData: {
      title: '',
      category: '其他',
      priority: 'medium',
      description: ''
    },
    showCreateModal: false
  },
  onLoad() {
    this.loadTickets(true)
  },
  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key }, () => {
      this.loadTickets(true)
    })
  },
  loadTickets(reset = false) {
    if (this.data.loading) return
    if (!reset && !this.data.hasMore) return
    this.setData({ loading: true })
    const page = reset ? 1 : this.data.page
    const params = { page, size: this.data.size }
    if (this.data.activeTab) params.status = this.data.activeTab
    api.get('/api/support-tickets/my', params).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      const formatted = list.map(t => ({
        ...t,
        status_text: STATUS_MAP[t.status] || t.status,
        priority_text: PRIORITY_MAP[t.priority] || t.priority
      }))
      this.setData({
        tickets: reset ? formatted : this.data.tickets.concat(formatted),
        page: page + 1,
        hasMore: list.length === this.data.size,
        loading: false
      })
    }).catch(() => {
      this.setData({ loading: false })
    })
  },
  onPullDownRefresh() {
    this.loadTickets(true)
    wx.stopPullDownRefresh()
  },
  onReachBottom() {
    this.loadTickets()
  },
  goDetail(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({ url: `/pages/support-ticket/detail/detail?id=${id}` })
  },
  openCreateModal() {
    this.setData({
      showCreateModal: true,
      formData: { title: '', category: '其他', priority: 'medium', description: '' }
    })
  },
  closeCreateModal() {
    this.setData({ showCreateModal: false })
  },
  onFormInput(e) {
    const { field } = e.currentTarget.dataset
    this.setData({ [`formData.${field}`]: e.detail.value })
  },
  onCategoryChange(e) {
    const categories = ['售后服务', '订单问题', '支付问题', '账户问题', '师傅投诉', '功能建议', '其他']
    const idx = e.detail.value
    this.setData({ 'formData.category': categories[idx] })
  },
  onPriorityChange(e) {
    const priorities = [{ key: 'low', label: '低' }, { key: 'medium', label: '中' }, { key: 'high', label: '高' }]
    const idx = e.detail.value
    this.setData({ 'formData.priority': priorities[idx].key })
  },
  submitTicket() {
    const { title, category, priority, description } = this.data.formData
    if (!title || !title.trim()) {
      wx.showToast({ title: '请输入标题', icon: 'none' })
      return
    }
    if (!description || !description.trim()) {
      wx.showToast({ title: '请输入问题描述', icon: 'none' })
      return
    }
    wx.showLoading({ title: '提交中...' })
    api.post('/api/support-tickets', { title: title.trim(), category, priority, description: description.trim() }).then(() => {
      wx.hideLoading()
      this.setData({ showCreateModal: false })
      wx.showToast({ title: '提交成功', icon: 'success' })
      this.loadTickets(true)
    }).catch(() => {
      wx.hideLoading()
    })
  },
  noop() {}
})

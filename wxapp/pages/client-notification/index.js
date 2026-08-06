const app = getApp()
const { createRuntimePage, displayTime, listFrom, messageOf } = require('../../utils/detail-page')

const TYPE_META = {
  order: { label: '订单', icon: '单' },
  system: { label: '系统', icon: '铃' },
  activity: { label: '活动', icon: '惠' }
}

Page(createRuntimePage({
  pageId: 'page-client-notification', route: 'pages/client-notification/index',
  source: 'pages/client-notification.html', sourceHash: 'fnv1a-6be7df06', title: '消息通知'
}, {
  data: { loading: true, loadError: '', messages: [], visibleMessages: [], unreadCount: 0, selectedType: '' },
  onShow() { this.loadMessages() },
  async loadMessages() {
    this.setData({ loading: true, loadError: '' })
    try {
      const result = await app.getApi().messages.list({ page: 1, size: 100 })
      const messages = listFrom(result).map(item => {
        const meta = TYPE_META[item.type] || { label: '消息', icon: '信' }
        return Object.assign({}, item, {
          typeText: meta.label, iconText: meta.icon,
          timeText: displayTime(item.created_at), unread: !item.is_read
        })
      })
      this.setData({
        loading: false,
        messages,
        unreadCount: Number(result && result.unread_count) || messages.filter(item => item.unread).length
      }, () => this.applyFilter())
    } catch (error) {
      this.setData({ loading: false, loadError: messageOf(error), messages: [], visibleMessages: [], unreadCount: 0 })
    }
  },
  onFilter(event) {
    const type = String(event.currentTarget.dataset.type || '')
    this.setData({ selectedType: this.data.selectedType === type ? '' : type }, () => this.applyFilter())
  },
  applyFilter() {
    const type = this.data.selectedType
    this.setData({ visibleMessages: type ? this.data.messages.filter(item => item.type === type) : this.data.messages })
  },
  onOpen(event) {
    const id = event.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/client-message-detail/index?id=' + encodeURIComponent(String(id)) })
  },
  async onMarkAllRead() {
    if (!this.data.unreadCount) return
    try {
      await app.getApi().messages.markAllRead()
      await this.loadMessages()
      wx.showToast({ title: '已全部标为已读', icon: 'success' })
    } catch (error) { wx.showToast({ title: messageOf(error, '操作失败'), icon: 'none' }) }
  }
}))

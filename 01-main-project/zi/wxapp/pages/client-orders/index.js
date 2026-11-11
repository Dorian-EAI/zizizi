// pages/client-orders/index.js — 客户端订单列表页（玻璃新拟态像素级复刻）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { STATUS_TEXT } = require('../../utils/order-status')

// 订单状态元信息：order-status-tag 样式类 + 操作按钮文案
// 对齐主样式规范的 .order-status-tag + .order-status-{status}
const STATUS_META = {
  pending:        { statusClass: 'order-status-pending',        actionText: '查看详情' },
  bidding:        { statusClass: 'order-status-bidding',        actionText: '查看报价' },
  accepted:       { statusClass: 'order-status-accepted',       actionText: '联系师傅' },
  departing:      { statusClass: 'order-status-departing',      actionText: '实时追踪' },
  arrived:        { statusClass: 'order-status-arrived',        actionText: '联系师傅' },
  serving:        { statusClass: 'order-status-serving',        actionText: '联系师傅' },
  completed:      { statusClass: 'order-status-completed',      actionText: '去支付' },
  paid:           { statusClass: 'order-status-paid',           actionText: '去评价' },
  reviewed:       { statusClass: 'order-status-reviewed',       actionText: '查看详情' },
  pending_review: { statusClass: 'order-status-pending-review', actionText: '去评价' },
  canceled:       { statusClass: 'order-status-canceled',       actionText: '查看详情' }
}

const ACTIVE_STATUSES = ['accepted', 'departing', 'arrived', 'serving']

Page({
  data: {
    statusBarHeight: 20,
    tabs: [
      { key: 'all', name: '全部' },
      { key: 'bidding', name: '竞价中' },
      { key: 'serving', name: '服务中' },
      { key: 'completed', name: '已完成' },
      { key: 'pending_review', name: '待评价' }
    ],
    activeTab: 'all',
    orders: [],
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        orders: buildIcon('orders', COLORS.text3),
        location: buildIcon('location', COLORS.text3),
        search: buildIcon('search', '#2C2824')
      }
    })
    this.loadData()
  },

  onShow() {
    // 角色可能切换，刷新 tab
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
    // 每次展示刷新订单
    this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    try {
      // 前端 tab key → 后端 Order.status（后端仅识别 pending/accepted/completed/paid/reviewed/cancelled）
      const STATUS_QUERY = {
        all: null,
        bidding: 'pending',        // 竞价中 = 待接单（待师傅报价）
        serving: 'accepted',       // 服务中 = 已接单进行中
        completed: 'completed',
        pending_review: 'paid'     // 待评价 = 已支付待评价
      }
      const queryStatus = STATUS_QUERY[this.data.activeTab]
      const rawOrders = await api.getClientOrders(queryStatus)
      // 附加状态元信息（后端 cancelled 双 l，前端字典为 canceled 单 l，需归一化用于展示）
      const ordersWithMeta = rawOrders.map(o => {
        const normStatus = o.status === 'cancelled' ? 'canceled' : o.status
        const meta = STATUS_META[normStatus] || {}
        return Object.assign({}, o, {
          statusText: o.statusText || STATUS_TEXT[normStatus] || '',
          statusClass: meta.statusClass,
          actionText: meta.actionText
        })
      })
      this.setData({ orders: ordersWithMeta })
    } catch (e) {
      console.error('加载订单失败', e)
    }
  },

  // 切换 Tab
  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key })
    this.loadData()
  },

  // 搜索按钮点击
  onSearchTap() {
    wx.navigateTo({ url: '/pages/search/index' })
  },

  // 点击订单卡 → 跳详情
  onOrderTap(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/order-detail-client/index?id=' + id })
  },

  // 点击底部操作按钮
  onActionTap(e) {
    const id = e.currentTarget.dataset.id
    const status = e.currentTarget.dataset.status
    // departing 状态 → 直接跳实时追踪页
    if (status === 'departing') {
      wx.navigateTo({ url: '/package-client/pages/client-order-tracking/index?orderId=' + id })
      return
    }
    // 其他状态 → 跳详情页（详情内可执行后续操作）
    wx.navigateTo({ url: '/pages/order-detail-client/index?id=' + id })
  }
})

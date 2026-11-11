// pages/worker-orders/index.js — 师傅端订单列表页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { STATUS_TEXT } = require('../../utils/order-status')

// 服务中步骤文案
const STEP_TEXT = {
  arrived: '已到达',
  diagnosing: '检测中',
  repairing: '维修中',
  done: '待客户验收'
}

// 状态元信息（与 order-status.js 状态枚举对齐）
const STATUS_META = {
  accepted:   { chipClass: 'chip-info',    actionText: '去出发' },
  departing:  { chipClass: 'chip-info',    actionText: '继续上报' },
  arrived:    { chipClass: 'chip-info',    actionText: '开始服务' },
  serving:    { chipClass: 'chip-info',    actionText: '去服务' },
  completed:  { chipClass: 'chip-success', actionText: '查看评价' },
  paid:       { chipClass: 'chip-success', actionText: '查看评价' },
  reviewed:   { chipClass: 'chip-success', actionText: '查看详情' },
  pending_review: { chipClass: 'chip-warning', actionText: '查看详情' }
}

// 状态徽章 CSS 类映射（对齐 worker-orders.html status-badge 配色）
const STATUS_BADGE_CLASS = {
  accepted:      'status-progress',
  departing:     'status-progress',
  arrived:       'status-progress',
  serving:       'status-progress',
  completed:     'status-done',
  paid:          'status-done',
  reviewed:      'status-done',
  pending_review:'status-pending'
}

// 价格标签文案映射（对齐 worker-orders.html price-label）
const PRICE_LABEL = {
  accepted:      '预计收入',
  departing:     '预计收入',
  arrived:       '预计收入',
  serving:       '预计收入',
  completed:     '实收',
  paid:          '实收',
  reviewed:      '实收',
  pending_review:'预计收入'
}

// 已完成状态集合（后端状态枚举：completed/paid/reviewed）
const DONE_STATUSES = ['completed', 'paid', 'reviewed', 'pending_review']

// 进行中状态集合
const ACTIVE_STATUSES = ['accepted', 'departing', 'arrived', 'serving']

Page({
  data: {
    statusBarHeight: 20,
    tabs: [
      { key: 'all',       name: '全部' },
      { key: 'active',    name: '进行中' },
      { key: 'completed', name: '已完成' }
    ],
    activeTab: 'all',
    orders: [],
    servingCount: 0,
    completedCount: 0,
    icons: {}
  },

  onLoad() {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        orders: buildIcon('orders', COLORS.text3),
        location: buildIcon('location', COLORS.text3),
        clock: buildIcon('clock', COLORS.text3),
        user: buildIcon('user', COLORS.brandWorker),
        phone: buildIcon('phone', COLORS.brandWorker),
        filter: buildIcon('filter', COLORS.text1),
        arrowRight: buildIcon('arrowRight', COLORS.white)
      }
    })
    this.loadData()
  },

  onShow() {
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
    this.loadData()
  },

  async loadData() {
    const api = app.getApi()
    try {
      const all = await api.getWorkerOrders()
      // 只取进行中 / 已完成（排除 available 抢单）
      const mine = (all || []).filter(o => o.status !== 'available')
      const servingCount = mine.filter(o => ACTIVE_STATUSES.indexOf(o.status) >= 0).length
      const completedCount = mine.filter(o => DONE_STATUSES.indexOf(o.status) >= 0).length

      const tab = this.data.activeTab
      let filtered
      if (tab === 'all') {
        filtered = mine
      } else if (tab === 'active') {
        filtered = mine.filter(o => ACTIVE_STATUSES.indexOf(o.status) >= 0)
      } else {
        filtered = mine.filter(o => DONE_STATUSES.indexOf(o.status) >= 0)
      }

      const withMeta = filtered.map(o => {
        const meta = STATUS_META[o.status] || {}
        return Object.assign({}, o, {
          iconUrl: buildIcon(o.icon || 'orders', COLORS.brandWorker),
          statusText: o.statusText || STATUS_TEXT[o.status] || '',
          statusChipClass: meta.chipClass,
          statusBadgeClass: STATUS_BADGE_CLASS[o.status] || 'status-progress',
          priceLabel: PRICE_LABEL[o.status] || '预计收入',
          isGreen: DONE_STATUSES.indexOf(o.status) >= 0,
          actionText: meta.actionText,
          stepText: STEP_TEXT[o.step] || ''
        })
      })

      this.setData({
        orders: withMeta,
        servingCount,
        completedCount
      })
    } catch (e) {
      console.error('加载订单失败', e)
    }
  },

  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key })
    this.loadData()
  },

  // 筛选设置按钮
  onFilterSettings() {
    wx.showToast({ title: '筛选设置', icon: 'none' })
  },

  onOrderTap(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/order-detail-worker/index?id=' + id })
  },

  onActionTap(e) {
    const id = e.currentTarget.dataset.id
    const status = e.currentTarget.dataset.status
    // accepted / departing → 跳位置上报页
    if (status === 'accepted' || status === 'departing') {
      wx.navigateTo({ url: '/package-worker/pages/worker-location-report/index?orderId=' + id })
      return
    }
    // 其他状态 → 跳订单详情
    wx.navigateTo({ url: '/pages/order-detail-worker/index?id=' + id })
  }
})

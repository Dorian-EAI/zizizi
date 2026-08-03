const api = require('../../utils/request')

const STATUS_MAP = {
  pending: '待接单',
  bidding: '竞价中',
  accepted: '服务中',
  serving: '服务中',
  completed: '待评价',
  reviewed: '已完成',
  cancelled: '已取消'
}

const TABS = [
  { key: '', text: '全部' },
  { key: 'bidding', text: '竞价中' },
  { key: 'serving', text: '服务中' },
  { key: 'reviewed', text: '已完成' },
  { key: 'completed', text: '待评价' }
]

function getBadgeType(status) {
  const map = {
    pending: 'pending',
    bidding: 'bidding',
    accepted: 'serving',
    serving: 'serving',
    completed: 'done',
    reviewed: 'done',
    cancelled: 'pending'
  }
  return map[status] || 'pending'
}

function getActionIcon(status) {
  const map = {
    pending: '/assets/svg/clock.svg',
    bidding: '/assets/svg/chevron-right.svg',
    accepted: '/assets/svg/phone.svg',
    serving: '/assets/svg/phone.svg',
    completed: '/assets/svg/award.svg',
    reviewed: '/assets/svg/chevron-right.svg',
    cancelled: '/assets/svg/plus.svg'
  }
  return map[status] || '/assets/svg/chevron-right.svg'
}

function getActionText(status) {
  const map = {
    pending: '等待接单',
    bidding: '查看报价',
    accepted: '联系师傅',
    serving: '联系师傅',
    completed: '评价师傅',
    reviewed: '查看详情',
    cancelled: '重新下单'
  }
  return map[status] || '查看详情'
}

function getInfoMain(status) {
  const map = {
    pending: '等待师傅接单',
    bidding: '已有 3 位师傅报价',
    accepted: '张师傅正在服务',
    serving: '师傅正在服务中',
    completed: '服务已完成',
    reviewed: '服务已完成',
    cancelled: '订单已取消'
  }
  return map[status] || ''
}

function getInfoPrice(status) {
  const map = {
    pending: '',
    bidding: '¥128-268',
    accepted: '',
    serving: '',
    completed: '',
    reviewed: '已支付 ¥128',
    cancelled: ''
  }
  return map[status] || ''
}

function getServiceName(status) {
  const map = {
    pending: '厨房水管漏水维修',
    bidding: '厨房水管漏水维修',
    accepted: '空调不制冷维修',
    serving: '空调不制冷维修',
    completed: '门锁更换',
    reviewed: '门锁更换',
    cancelled: '水电维修'
  }
  return map[status] || '维修服务'
}

function getAddress(status) {
  const map = {
    pending: '北京市朝阳区建国路88号院3号楼',
    bidding: '北京市朝阳区建国路88号院3号楼',
    accepted: '北京市海淀区中关村大街1号',
    serving: '北京市海淀区中关村大街1号',
    completed: '北京市西城区西直门外大街18号',
    reviewed: '北京市西城区西直门外大街18号',
    cancelled: '北京市朝阳区建国路88号院'
  }
  return map[status] || ''
}

function getDate(status) {
  const map = {
    pending: '刚刚',
    bidding: '2024-06-20 14:30',
    accepted: '2024-06-19 09:00',
    serving: '2024-06-19 09:00',
    completed: '2024-06-15 16:20',
    reviewed: '2024-06-15 16:20',
    cancelled: '2024-06-10 11:00'
  }
  return map[status] || ''
}

Page({
  data: {
    filterTabs: TABS,
    activeTab: '',
    orders: [],
    page: 1,
    size: 10,
    hasMore: true,
    loading: false
  },

  onLoad(options) {
    if (options.status) this.setData({ activeTab: options.status })
    this.loadOrders(true)
  },

  onShow() {
    this.loadOrders(true)
  },

  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key })
    this.loadOrders(true)
  },

  loadOrders(reset) {
    if (this.data.loading) return
    if (!reset && !this.data.hasMore) return
    this.setData({ loading: true })
    const page = reset ? 1 : this.data.page
    const params = { page, size: this.data.size, role: 'user' }
    if (this.data.activeTab) params.status = this.data.activeTab

    api.get('/api/orders', params).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      const orders = list.map(o => {
        const status = o.status || 'pending'
        return {
          ...o,
          service_name: o.service_name || getServiceName(status),
          status_text: STATUS_MAP[status] || status,
          badge_type: getBadgeType(status),
          date: o.date || getDate(status),
          address: o.address || getAddress(status),
          info_main: o.info_main || getInfoMain(status),
          info_price: o.info_price || getInfoPrice(status),
          action_icon: getActionIcon(status),
          action_text: getActionText(status)
        }
      })

      if (orders.length === 0 && reset) {
        const demoOrders = this.getDemoOrders()
        this.setData({
          orders: demoOrders,
          page: 2,
          hasMore: false,
          loading: false
        })
      } else {
        this.setData({
          orders: reset ? orders : this.data.orders.concat(orders),
          page: page + 1,
          hasMore: list.length === this.data.size,
          loading: false
        })
      }
    }).catch(() => {
      if (reset) {
        const demoOrders = this.getDemoOrders()
        this.setData({ orders: demoOrders, loading: false })
      } else {
        this.setData({ loading: false })
      }
    })
  },

  getDemoOrders() {
    return [
      {
        id: 'demo-1',
        status: 'bidding',
        service_name: '厨房水管漏水维修',
        status_text: '竞价中',
        badge_type: 'bidding',
        date: '2024-06-20 14:30',
        address: '北京市朝阳区建国路88号院3号楼',
        info_main: '已有 3 位师傅报价',
        info_price: '¥128-268',
        action_icon: '/assets/svg/chevron-right.svg',
        action_text: '查看报价'
      },
      {
        id: 'demo-2',
        status: 'serving',
        service_name: '空调不制冷维修',
        status_text: '服务中',
        badge_type: 'serving',
        date: '2024-06-19 09:00',
        address: '北京市海淀区中关村大街1号',
        info_main: '张师傅正在服务',
        info_price: '',
        action_icon: '/assets/svg/phone.svg',
        action_text: '联系师傅'
      },
      {
        id: 'demo-3',
        status: 'completed',
        service_name: '门锁更换',
        status_text: '已完成',
        badge_type: 'done',
        date: '2024-06-15 16:20',
        address: '北京市西城区西直门外大街18号',
        info_main: '服务已完成',
        info_price: '',
        action_icon: '/assets/svg/award.svg',
        action_text: '评价师傅'
      }
    ]
  },

  onSearch() {
    wx.navigateTo({ url: '/pages/search/search' })
  },

  onPullDownRefresh() {
    this.loadOrders(true)
    wx.stopPullDownRefresh()
  },

  onReachBottom() {
    this.loadOrders()
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/order/detail/detail?id=${id}` })
  }
})
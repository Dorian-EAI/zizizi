const api = require('../../../utils/request')

const WORKER_TABS = [
  { key: 'home', text: '首页', path: '/pages/worker/index/index' },
  { key: 'orders', text: '订单', path: '/pages/worker/orders/orders' },
  { key: 'review', text: '评价', path: '/pages/review/list/list' },
  { key: 'mine', text: '我的', path: '/pages/worker/profile/profile' }
]

const STATUS_MAP = {
  pending: '待接单',
  accepted: '待出发',
  departing: '前往中',
  arrived: '已到达',
  serving: '服务中',
  completed: '待支付',
  paid: '待评价',
  reviewed: '已完成',
  cancelled: '已取消'
}

const LOCATION_REPORT_INTERVAL = 15000
const IN_PROGRESS_STATUSES = ['accepted', 'departing', 'arrived', 'serving']

Page({
  data: {
    tabs: [
      { key: 'active', text: '进行中' },
      { key: 'completed', text: '待支付' },
      { key: 'reviewed', text: '已完成' }
    ],
    activeTab: 'active',
    orders: [],
    loading: false,
    currentTab: 'orders',
    tabBar: WORKER_TABS,
    statusMap: STATUS_MAP,
    locationReportTimer: null,
    reportingLocation: false,
    departingOrderId: null
  },
  onLoad() {
    this.loadOrders(true)
  },
  onShow() {
    this.loadOrders(true)
  },
  onHide() {
    this.stopLocationReporting()
  },
  onUnload() {
    this.stopLocationReporting()
  },
  onTabTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key })
    this.loadOrders(true)
  },
  loadOrders(reset = false) {
    if (this.data.loading) return
    this.setData({ loading: true })
    const params = { role: 'worker', page: 1, size: 20 }
    if (this.data.activeTab !== 'active') {
      params.status = this.data.activeTab
    }
    api.get('/api/orders', params).then(data => {
      const list = Array.isArray(data) ? data : (data.list || [])
      let filtered = list
      if (this.data.activeTab === 'active') {
        filtered = list.filter(o => IN_PROGRESS_STATUSES.indexOf(o.status) !== -1)
      }
      const orders = filtered.map(o => ({
        ...o,
        status_text: STATUS_MAP[o.status] || o.status
      }))
      this.setData({ orders: reset ? orders : this.data.orders.concat(orders), loading: false })
      this.checkDepartingOrder(orders)
    }).catch(() => {
      const mockOrders = this.getMockOrders()
      let filtered = mockOrders
      if (this.data.activeTab === 'active') {
        filtered = mockOrders.filter(o => IN_PROGRESS_STATUSES.indexOf(o.status) !== -1)
      } else if (this.data.activeTab === 'completed') {
        filtered = mockOrders.filter(o => o.status === 'completed' || o.status === 'paid')
      } else if (this.data.activeTab === 'reviewed') {
        filtered = mockOrders.filter(o => o.status === 'reviewed')
      }
      const orders = filtered.map(o => ({
        ...o,
        status_text: STATUS_MAP[o.status] || o.status
      }))
      this.setData({ orders, loading: false })
      this.checkDepartingOrder(orders)
    })
  },
  getMockOrders() {
    return [
      { id: '101', status: 'accepted', service_name: '冰箱不制冷维修', contact_name: '张女士', contact_phone_text: '138****6789', address: '北京市朝阳区望京SOHO T1', final_price: '280' },
      { id: '102', status: 'departing', service_name: '空调安装', contact_name: '李先生', contact_phone_text: '139****1234', address: '北京市海淀区中关村大街1号', final_price: '350' },
      { id: '103', status: 'arrived', service_name: '水电检修', contact_name: '王阿姨', contact_phone_text: '137****5678', address: '北京市西城区金融街3号', final_price: '168' },
      { id: '104', status: 'paid', service_name: '水管疏通', contact_name: '赵先生', contact_phone_text: '135****9012', address: '北京市东城区建国路88号', final_price: '120' },
      { id: '105', status: 'reviewed', service_name: '门窗维修', contact_name: '孙女士', contact_phone_text: '136****3456', address: '北京市丰台区丽泽商务区', final_price: '95' }
    ]
  },
  // 检查是否有出发中的订单，自动启停位置上报
  checkDepartingOrder(orders) {
    const departing = orders.find(o => o.status === 'departing')
    if (departing) {
      this.setData({ departingOrderId: departing.id, reportingLocation: true })
      this.startLocationReporting()
    } else {
      this.stopLocationReporting()
      this.setData({ reportingLocation: false, departingOrderId: null })
    }
  },
  // 出发
  departOrder(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认出发',
      content: '确认开始前往客户地址吗？系统将开始上报您的位置。',
      success: res => {
        if (res.confirm) {
          api.post(`/api/worker/orders/${id}/depart`).then(() => {
            wx.showToast({ title: '已出发，注意安全' })
            this.setData({ departingOrderId: id, reportingLocation: true })
            this.startLocationReporting()
            this.loadOrders(true)
          }).catch(() => wx.showToast({ title: '操作失败', icon: 'none' }))
        }
      }
    })
  },
  // 到达
  arriveOrder(e) {
    const id = e.currentTarget.dataset.id
    wx.getLocation({
      type: 'gcj02',
      success: (loc) => {
        api.post(`/api/worker/orders/${id}/arrive`, {
          latitude: loc.latitude,
          longitude: loc.longitude
        }).then(() => {
          wx.showToast({ title: '已确认到达' })
          this.stopLocationReporting()
          this.setData({ reportingLocation: false, departingOrderId: null })
          this.loadOrders(true)
        }).catch(() => wx.showToast({ title: '操作失败', icon: 'none' }))
      },
      fail: () => {
        wx.showToast({ title: '获取定位失败，请检查权限', icon: 'none' })
      }
    })
  },
  // 开始服务
  startService(e) {
    const id = e.currentTarget.dataset.id
    wx.getLocation({
      type: 'gcj02',
      success: (loc) => {
        api.post(`/api/worker/orders/${id}/start-service`, {
          latitude: loc.latitude,
          longitude: loc.longitude
        }).then(() => {
          wx.showToast({ title: '服务已开始' })
          this.loadOrders(true)
        }).catch(() => wx.showToast({ title: '操作失败', icon: 'none' }))
      },
      fail: () => {
        wx.showToast({ title: '获取定位失败，请检查权限', icon: 'none' })
      }
    })
  },
  // 完工
  completeOrder(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '完工确认',
      editable: true,
      placeholderText: '请输入本次服务成交价',
      success: res => {
        if (res.confirm) {
          const price = parseFloat(res.content)
          if (!price || price <= 0) {
            wx.showToast({ title: '请输入有效金额', icon: 'none' })
            return
          }
          api.put(`/api/orders/${id}/status`, { status: 'completed', price }).then(() => {
            wx.showToast({ title: '已提交完工' })
            this.loadOrders(true)
          }).catch(() => wx.showToast({ title: '操作失败', icon: 'none' }))
        }
      }
    })
  },
  // 启动位置上报
  startLocationReporting() {
    if (this.data.locationReportTimer) return
    this.reportLocation()
    const timer = setInterval(() => {
      this.reportLocation()
    }, LOCATION_REPORT_INTERVAL)
    this.setData({ locationReportTimer: timer })
  },
  // 停止位置上报
  stopLocationReporting() {
    if (this.data.locationReportTimer) {
      clearInterval(this.data.locationReportTimer)
      this.setData({ locationReportTimer: null })
    }
  },
  // 上报位置
  reportLocation() {
    wx.getLocation({
      type: 'gcj02',
      success: (loc) => {
        api.post('/api/worker/location/report', {
          latitude: loc.latitude,
          longitude: loc.longitude,
          heading: loc.heading || 0,
          speed: loc.speed || 0
        }).catch(() => {})
      },
      fail: () => {}
    })
  },
  contactCustomer(e) {
    const phone = e.currentTarget.dataset.phone
    if (phone) {
      wx.makePhoneCall({ phoneNumber: phone })
    } else {
      wx.showToast({ title: '暂无联系电话', icon: 'none' })
    }
  },
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/worker/detail/detail?order_id=${id}` })
  },
  onTabbarTap(e) {
    const path = e.currentTarget.dataset.path
    if (path === '/pages/review/list/list') {
      wx.navigateTo({ url: path })
      return
    }
    wx.redirectTo({ url: path })
  }
})

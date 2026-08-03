const api = require('../../../utils/request')

const POLL_INTERVAL = 10000

// 终态订单：服务已完成及之后的状态，停止轮询
const TERMINAL_STATUSES = ['completed', 'paid', 'reviewed', 'cancelled']

// 不同订单状态下的横幅文案
const STATUS_BANNER = {
  accepted: '等待师傅出发',
  departing: '师傅正在赶来',
  arrived: '师傅已到达',
  serving: '师傅正在服务中',
  completed: '服务已完成',
  paid: '服务已完成',
  reviewed: '服务已完成',
  cancelled: '订单已取消'
}

Page({
  data: {
    orderId: null,
    loading: true,
    orderStatus: '',
    serviceName: '',
    statusText: '',
    bannerText: '',
    etaText: '',
    distanceText: '',
    worker: null,
    location: null,
    eta: null,
    destination: null,
    timeline: [],
    markers: [],
    polyline: [],
    mapCenter: { latitude: 0, longitude: 0 },
    showStaleWarn: false,
    isTerminal: false
  },

  onLoad(options) {
    const id = options.order_id || options.id
    if (!id) {
      wx.showToast({ title: '缺少订单参数', icon: 'none' })
      return
    }
    this.setData({ orderId: id })
    this.loadTracking()
  },

  onShow() {
    // 页面再次显示时恢复轮询（已结束的订单不轮询）
    if (this.data.orderId && !this.data.isTerminal && !this._timer) {
      this.startPolling()
    }
  },

  onHide() {
    this.stopPolling()
  },

  onUnload() {
    this.stopPolling()
  },

  startPolling() {
    this.stopPolling()
    this._timer = setInterval(() => {
      this.loadTracking(true)
    }, POLL_INTERVAL)
  },

  stopPolling() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },

  loadTracking(silent) {
    if (!this.data.orderId) return
    api.get(`/api/orders/${this.data.orderId}/tracking`).then(data => {
      if (!data) return
      const isTerminal = TERMINAL_STATUSES.indexOf(data.order_status) >= 0
      const bannerText = STATUS_BANNER[data.order_status] || data.status_text || ''
      const etaText = (data.eta && data.eta.eta_text) || ''
      const distanceText = (data.eta && data.eta.distance_text) || ''

      // 状态文案覆盖（按需求精修）
      let statusText = data.status_text || bannerText
      if (data.order_status === 'accepted') statusText = '等待师傅出发'
      else if (data.order_status === 'arrived') statusText = '师傅已到达'
      else if (data.order_status === 'serving') statusText = '师傅正在服务中'
      else if (isTerminal) statusText = '服务已完成'

      this.setData({
        loading: false,
        orderStatus: data.order_status,
        serviceName: data.service_name || '',
        statusText,
        bannerText,
        etaText,
        distanceText,
        worker: data.worker || null,
        location: data.location || null,
        eta: data.eta || null,
        destination: data.destination || null,
        timeline: Array.isArray(data.timeline) ? data.timeline : [],
        showStaleWarn: !!(data.location && data.location.is_stale)
      })

      this.buildMapData(data)

      if (isTerminal) {
        this.stopPolling()
        this.setData({ isTerminal: true })
      } else {
        this.startPolling()
      }
    }).catch(() => {
      if (!silent) {
        wx.showToast({ title: '加载失败', icon: 'none' })
      }
    })
  },

  buildMapData(data) {
    const markers = []
    const worker = data.location
    const dest = data.destination

    // 师傅位置标记（绿色）
    if (worker && worker.latitude && worker.longitude) {
      markers.push({
        id: 1,
        latitude: worker.latitude,
        longitude: worker.longitude,
        iconPath: '/assets/marker-green.png',
        width: 32,
        height: 32,
        callout: {
          content: '师傅位置',
          color: '#ffffff',
          fontSize: 12,
          bgColor: '#07c160',
          borderRadius: 8,
          padding: 6,
          display: 'ALWAYS'
        }
      })
    }

    // 服务地点标记（红色）
    if (dest && dest.latitude && dest.longitude) {
      markers.push({
        id: 2,
        latitude: dest.latitude,
        longitude: dest.longitude,
        iconPath: '/assets/marker-red.png',
        width: 32,
        height: 32,
        callout: {
          content: '服务地点',
          color: '#ffffff',
          fontSize: 12,
          bgColor: '#e64340',
          borderRadius: 8,
          padding: 6,
          display: 'ALWAYS'
        }
      })
    }

    // 行驶轨迹折线
    let polyline = []
    const routePoints = Array.isArray(data.route_points) ? data.route_points : []
    if (routePoints.length > 1) {
      polyline = [{
        points: routePoints.map(p => ({ latitude: p.latitude, longitude: p.longitude })),
        color: '#004080',
        width: 6
      }]
    }

    // 地图中心：优先跟随师傅位置，否则使用服务地点
    let mapCenter = { latitude: 0, longitude: 0 }
    if (worker && worker.latitude && worker.longitude) {
      mapCenter = { latitude: worker.latitude, longitude: worker.longitude }
    } else if (dest && dest.latitude && dest.longitude) {
      mapCenter = { latitude: dest.latitude, longitude: dest.longitude }
    }

    this.setData({ markers, polyline, mapCenter })
  },

  callWorker() {
    const phone = this.data.worker && this.data.worker.phone
    if (!phone) {
      wx.showToast({ title: '暂无师傅电话', icon: 'none' })
      return
    }
    wx.makePhoneCall({ phoneNumber: phone })
  },

  openNavigation() {
    const dest = this.data.destination
    if (!dest || !dest.latitude || !dest.longitude) {
      wx.showToast({ title: '暂无服务地点', icon: 'none' })
      return
    }
    wx.openLocation({
      latitude: parseFloat(dest.latitude),
      longitude: parseFloat(dest.longitude),
      name: this.data.serviceName || '服务地点',
      address: this.data.serviceName || '服务地点',
      scale: 18
    })
  }
})

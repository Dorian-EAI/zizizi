// pages/client-order-tracking/index.js — 用户端实时追踪页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { STATUS_TEXT, TRACKING_STEPS, getStepIndex } = require('../../utils/order-status')

// 位置过期阈值（毫秒）：超过 60 秒未更新则提示
const STALE_THRESHOLD = 60 * 1000
// 轮询间隔：10 秒
const POLL_INTERVAL = 10000

const TRACKING_STATUS_TITLE = {
  accepted: '师傅准备出发',
  departing: '师傅正在赶来',
  arrived: '师傅已到达',
  serving: '师傅正在服务',
  completed: '服务已完成',
  paid: '等待评价',
  reviewed: '订单已完成'
}

// 时间线节点默认描述（HTML 参考值）
const STEP_DESC = {
  accepted: '师傅已确认接单，准备出发',
  departing: '师傅已离开上一服务地点',
  arrived: '师傅正在赶来',
  serving: '等待师傅到场后开始',
  completed: '服务完成后请验收确认'
}

Page({
  data: {
    statusBarHeight: 20,
    orderId: '',
    tracking: {},
    mapLat: 0,
    mapLng: 0,
    markers: [],
    polyline: [],
    steps: [],
    staleWarning: false,
    loading: true,
    loadError: false,
    statusTitle: '位置状态待加载',
    statusMeta: '',
    icons: {},
    // ===== 滚动变形状态（忠于 HTML 参考脚本 syncMorph，1px=2rpx） =====
    morphP: 0,           // 形变进度 0~1（y/120）
    morphed: false,      // y>60：nav-bar 完全扩张为 top-header
    statusFixed: false,  // y>80：状态横幅从地图底部漂浮到 nav-bar 内
    navTitleSize: 34,    // 17px→34rpx + 10rpx*morphP（17px→22px）
    navRadius: 64,       // 32px→64rpx + 8rpx*morphP（32px→36px）
    navPh: 40,           // 20px→40rpx + 8rpx*morphP（20px→24px）
    navPb: 36,           // 18px→36rpx + 12rpx*morphP（18px→24px）
    btnSize: 80,         // 40px→80rpx - 8rpx*morphP（40px→36px）
    mapHeight: 420,      // 420px → max(120, 420-300*morphP) px
    mapScale: 1,         // 1 - 0.08*morphP
    mapOpacity: 1,       // 1 - 0.7*morphP
    statusTranslate: 0,  // -106*morphP px（状态横幅上浮距离）
    statusMt: -32        // -32 + 14*morphP px（状态横幅 margin-top）
  },

  onLoad(query) {
    const orderId = query && query.orderId ? query.orderId : (query && query.id)
    this.setData({
      orderId,
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        phone: buildIcon('phone', COLORS.brand),
        location: buildIcon('location', COLORS.brand),
        navigation: buildIcon('navigation', COLORS.accentDark),
        star: buildIcon('star', COLORS.accent),
        check: buildIcon('check', COLORS.white),
        user: buildIcon('user', COLORS.text3),
        refresh: buildIcon('refresh', COLORS.text1),
        arrowRight: buildIcon('arrowRight', COLORS.text2)
      }
    })
    this.loadTracking()
  },

  onShow() {
    this.startPolling()
  },

  onHide() {
    this.stopPolling()
  },

  onUnload() {
    this.stopPolling()
  },

  startPolling() {
    this.stopPolling()
    this._timer = setInterval(() => this.loadTracking(), POLL_INTERVAL)
  },

  stopPolling() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },

  async loadTracking() {
    const api = app.getApi()
    try {
      const data = await api.track.tracking(this.data.orderId)
      if (!data || !(data.status || data.order_status)) throw new Error('追踪接口未返回有效订单状态')
      this.applyTracking(data)
      this.setData({ loading: false, loadError: false })
    } catch (e) {
      console.error('加载追踪数据失败', e)
      this.setData({ loading: false, loadError: true })
    }
  },

  onRetry() {
    this.setData({ loading: true, loadError: false })
    this.loadTracking()
  },

  applyTracking(data) {
    const rawTracking = data || {}
    const rawLocation = rawTracking.location || {}
    const rawDestination = rawTracking.destination || {}
    const rawWorker = rawTracking.worker || null
    const workerLat = Number(rawWorker && (rawWorker.lat || rawWorker.latitude)) || Number(rawLocation.latitude || rawLocation.lat) || 0
    const workerLng = Number(rawWorker && (rawWorker.lng || rawWorker.longitude)) || Number(rawLocation.longitude || rawLocation.lng) || 0
    const destLat = Number(rawDestination.lat || rawDestination.latitude) || 0
    const destLng = Number(rawDestination.lng || rawDestination.longitude) || 0
    const worker = rawWorker ? Object.assign({}, rawWorker, {
      lat: workerLat,
      lng: workerLng,
      rating: Number(rawWorker.rating) > 0 ? rawWorker.rating : '—',
      services: rawWorker.services != null
        ? rawWorker.services
        : (rawWorker.service_count != null ? rawWorker.service_count : '—'),
      certified: rawWorker.certified == null ? null : Number(rawWorker.certified) === 2
    }) : {}
    const dest = (destLat && destLng) ? Object.assign({}, rawDestination, { lat: destLat, lng: destLng }) : null
    const timelineMap = {}
    ;(Array.isArray(rawTracking.timeline) ? rawTracking.timeline : []).forEach(item => {
      if (item && (item.status || item.key)) timelineMap[item.status || item.key] = item.time || ''
    })
    const tracking = Object.assign({}, rawTracking, {
      status: rawTracking.status || rawTracking.order_status,
      worker: rawWorker ? worker : null,
      destination: dest,
      route: rawTracking.route || rawTracking.route_points || [],
      lastUpdate: rawTracking.lastUpdate || rawTracking.last_update || rawLocation.last_reported_at,
      steps: rawTracking.steps || timelineMap
    })
    if (!(workerLat && workerLng) && !(destLat && destLng)) {
      throw new Error('追踪接口未返回有效坐标')
    }

    // 构建 markers：师傅位置（蓝）+ 服务地点（红）
    // 不依赖本地图片资源，避免小程序包缺少 /assets 时地图标记丢失。
    const markers = []
    if (workerLat && workerLng) {
      markers.push({
        id: 1,
        latitude: workerLat,
        longitude: workerLng,
        title: worker.name || '师傅位置',
        callout: {
          content: worker.name || '师傅位置',
          color: '#2C2824',
          fontSize: 12,
          borderRadius: 8,
          bgColor: '#FFFFFFCC',
          padding: 8,
          display: 'ALWAYS'
        },
        width: 44,
        height: 44
      })
    }
    if (destLat && destLng) {
      markers.push({
        id: 2,
        latitude: destLat,
        longitude: destLng,
        title: dest.name || '服务地点',
        callout: {
          content: dest.name || '服务地点',
          color: '#2C2824',
          fontSize: 12,
          borderRadius: 8,
          bgColor: '#FFFFFFCC',
          padding: 8,
          display: 'BYCLICK'
        },
        width: 36,
        height: 36
      })
    }

    // polyline：优先使用历史轨迹，没有则用师傅位置到目的地的连线兜底
    const polyline = []
    const route = tracking.route || tracking.routeHistory || tracking.history || []
    const routePoints = route.map(function (p) {
      return {
        latitude: Number(p.latitude || p.lat),
        longitude: Number(p.longitude || p.lng)
      }
    }).filter(function (p) {
      return p.latitude && p.longitude
    })
    if (routePoints.length >= 2) {
      polyline.push({
        points: routePoints,
        color: '#2D6CDFFF',
        width: 6,
        dottedLine: false,
        arrowLine: true
      })
    } else if (workerLat && workerLng && destLat && destLng) {
      polyline.push({
        points: [
          { latitude: workerLat, longitude: workerLng },
          { latitude: destLat, longitude: destLng }
        ],
        color: '#2D6CDFFF',
        width: 6,
        dottedLine: false
      })
    }

    // 位置是否超过 60 秒未更新
    const lastUpdateValue = tracking.lastUpdate
    const lastUpdate = lastUpdateValue ? new Date(lastUpdateValue).getTime() : 0
    const staleWarning = !!(workerLat && workerLng) && (rawLocation.is_stale === true || !lastUpdate || (Date.now() - lastUpdate) > STALE_THRESHOLD)

    // 服务进度时间线（state: done/active/pending，desc: HTML 参考描述）
    const status = tracking.status
    const currentIdx = getStepIndex(status)
    const distanceText = (function () {
      const eta = tracking.eta || {}
      const d = eta.distance || eta.distance_text || tracking.distance
      return d ? ('，距离' + d) : ''
    })()
    const steps = TRACKING_STEPS.map(function (s, i) {
      const isDone = i < currentIdx
      const isActive = i === currentIdx
      let desc = STEP_DESC[s.key] || ''
      // arrived 步骤附加距离信息（HTML 参考：师傅正在赶来，距离1.5km）
      if (s.key === 'arrived' && isActive && distanceText) {
        desc = desc + distanceText
      }
      return {
        key: s.key,
        title: s.title,
        state: isDone ? 'done' : (isActive ? 'active' : 'pending'),
        done: isDone,
        active: isActive,
        time: (tracking.steps && tracking.steps[s.key]) || '',
        desc: desc
      }
    })

    // 状态横幅文案
    const eta = tracking.eta || {}
    const statusTitle = TRACKING_STATUS_TITLE[status] || STATUS_TEXT[status] || '订单状态待确认'
    const metaParts = []
    const etaSeconds = eta.eta_seconds || tracking.eta_seconds
    const etaMinutes = eta.minutes || tracking.etaMinutes || (etaSeconds ? Math.ceil(Number(etaSeconds) / 60) : '')
    const distance = eta.distance || eta.distance_text || tracking.distance ||
      (eta.distance_meters ? (Number(eta.distance_meters) / 1000).toFixed(1) + 'km' : '')
    if (eta.eta_text) metaParts.push(eta.eta_text)
    else if (etaMinutes) metaParts.push('约' + etaMinutes + '分钟到达')
    if (distance) metaParts.push(distance)
    const statusMeta = metaParts.join(' · ')

    this.setData({
      tracking,
      mapLat: workerLat || destLat,
      mapLng: workerLng || destLng,
      markers,
      polyline,
      steps,
      staleWarning,
      statusTitle,
      statusMeta
    })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onCallWorker() {
    const phone = this.data.tracking.worker && this.data.tracking.worker.phone
    const value = String(phone || '').trim()
    if (!value || value.indexOf('*') >= 0 || !/^1[3-9]\d{9}$/.test(value)) {
      wx.showToast({ title: '师傅电话未提供或已脱敏', icon: 'none' })
      return
    }
    wx.makePhoneCall({ phoneNumber: value })
  },

  onNavigate() {
    const dest = this.data.tracking.destination
    if (!dest || !dest.lat || !dest.lng) {
      wx.showToast({ title: '暂无目的地坐标', icon: 'none' })
      return
    }
    wx.openLocation({
      latitude: Number(dest.lat),
      longitude: Number(dest.lng),
      name: dest.name || '服务地点',
      address: dest.address || ''
    })
  },

  async onCancelOrder() {
    const confirm = await new Promise(function (resolve) {
      wx.showModal({
        title: '取消订单',
        content: '确定要取消此订单吗？',
        confirmText: '取消订单',
        cancelText: '再想想',
        confirmColor: '#DC2626',
        success: function (r) { resolve(r.confirm) }
      })
    })
    if (!confirm) return
    wx.showLoading({ title: '处理中...' })
    const api = app.getApi()
    try {
      await api.orders.cancel(this.data.orderId)
      wx.hideLoading()
      wx.showToast({ title: '订单已取消', icon: 'success' })
      this.stopPolling()
      setTimeout(function () { wx.navigateBack({ delta: 1 }) }, 1000)
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '取消失败', icon: 'none' })
    }
  },

  // ===== 滚动变形：nav-bar → top-header，地图收缩，状态横幅上浮 =====
  // 忠于 HTML 参考脚本 syncMorph（小程序动画与布局实现规范.md 第 2.2 节）
  // morphP = y/120（0~1）；nav-bar 阈值 60px；状态横幅固定阈值 80px
  onTrackingScroll(e) {
    const y = (e.detail && e.detail.scrollTop) || 0
    const morphP = Math.min(Math.max(y / 120, 0), 1)
    // 量化到 2 位小数，避免微小滚动触发频繁 setData
    const roundedP = Math.round(morphP * 100) / 100
    const morphed = y > 60
    const statusFixed = y > 80

    // 仅在 morphP 或 statusFixed 变化时更新
    if (this._lastMorphP === roundedP && this._lastStatusFixed === statusFixed) return
    this._lastMorphP = roundedP
    this._lastStatusFixed = statusFixed

    this.setData({
      morphP: roundedP,
      morphed: morphed,
      statusFixed: statusFixed,
      // nav-bar 形变（1px=2rpx：原值×2）
      navTitleSize: 34 + 10 * roundedP,   // 17px→34rpx + 5px→10rpx * p
      navRadius: 64 + 8 * roundedP,       // 32px→64rpx + 4px→8rpx * p
      navPh: 40 + 8 * roundedP,           // 20px→40rpx + 4px→8rpx * p
      navPb: 36 + 12 * roundedP,          // 18px→36rpx + 6px→12rpx * p
      btnSize: 80 - 8 * roundedP,         // 40px→80rpx - 4px→8rpx * p
      // 地图收缩（px 单位，直接用于 height）
      mapHeight: Math.max(120, 420 - 300 * roundedP),
      mapScale: 1 - 0.08 * roundedP,
      mapOpacity: 1 - 0.7 * roundedP,
      // 状态横幅上浮（px 单位）
      statusTranslate: -106 * roundedP,
      statusMt: -32 + 14 * roundedP
    })
  },

  onRefresh() {
    this.setData({ loading: true, loadError: false })
    this.loadTracking()
  },

  onViewOrderDetail() {
    const orderId = this.data.orderId
    if (orderId) {
      wx.navigateTo({ url: '/pages/order-detail-client/index?orderId=' + orderId })
    } else {
      wx.navigateBack({ delta: 1 })
    }
  }
})

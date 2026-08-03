// pages/worker-location-report/index.js — 师傅端位置上报页
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

// 上报间隔：15 秒；连续失败上限：3 次
const REPORT_INTERVAL = 15000
const MAX_FAIL_COUNT = 3

Page({
  data: {
    statusBarHeight: 20,
    orderId: '',
    order: {},
    currentLat: 0,
    currentLng: 0,
    lastReportTime: '',
    reporting: false,
    permissionDenied: false,
    failCount: 0,
    icons: {}
  },

  onLoad(query) {
    const orderId = query && query.orderId ? query.orderId : (query && query.id)
    this.setData({
      orderId,
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('chevronLeft', COLORS.text1),
        location: buildIcon('location', COLORS.brandWorker),
        clock: buildIcon('clock', COLORS.text3),
        wrench: buildIcon('carpentry', COLORS.text3),
        user: buildIcon('user', COLORS.text3),
        addrIcon: buildIcon('location', COLORS.text3),
        calendar: buildIcon('calendar', COLORS.text3),
        phone: buildIcon('phone', COLORS.brandWorker),
        navigate: buildIcon('navigation', COLORS.brandWorker),
        check: buildIcon('location', COLORS.white)
      }
    })
    this.initializeReport()
  },

  onShow() {
    // 仅在已出发后恢复上报，避免与 onLoad 中的 depart 流程冲突
    if (this._departed) this.startReport()
  },

  onHide() {
    this.stopReport()
  },

  onUnload() {
    this.stopReport()
  },

  async loadOrder() {
    const api = app.getApi()
    try {
      // 后端无 /api/orders/worker/{id} 路由；通用详情 /api/orders/{id} 对已接单师傅开放（归属校验）
      const raw = await api.orders.detail(this.data.orderId)
      const order = this.mapOrder(raw || {})
      this.setData({ order })
      return order
    } catch (e) {
      console.error('加载订单失败', e)
      wx.showToast({ title: '订单加载失败', icon: 'none' })
      return null
    }
  },

  async initializeReport() {
    if (!this.data.orderId) {
      wx.showToast({ title: '缺少订单信息', icon: 'none' })
      return
    }
    const order = await this.loadOrder()
    if (!order) return
    if (order.status === 'departing') {
      this._departed = true
      this.startReport()
      return
    }
    if (order.status === 'accepted') {
      await this.departAndStartReport()
      return
    }
    wx.showToast({ title: '当前订单状态无法开启位置上报', icon: 'none' })
  },

  // 后端 OrderResponse(snake_case) → 前端 wxml 期望(camelCase)
  mapOrder(raw) {
    if (!raw) return {}
    const addr = this.parseAddress(raw.address)
    return Object.assign({}, raw, {
      serviceName: raw.serviceName || raw.service_name || raw.service_type || '',
      address: addr.address || raw.address || '',
      lat: raw.lat != null ? raw.lat : addr.lat,
      lng: raw.lng != null ? raw.lng : addr.lng,
      appointmentTime: raw.appointmentTime || this.formatDate(raw.appoint_time),
      time: raw.time || this.formatDate(raw.appoint_time),
      userName: raw.userName || raw.user_name || '',
      userPhone: raw.userPhone || raw.user_phone || ''
    })
  },

  // 解析后端 address 字段（JSON {address,latitude,longitude} 或纯文本）
  parseAddress(addrStr) {
    if (!addrStr) return { address: '', lat: null, lng: null }
    if (typeof addrStr === 'object') {
      return {
        address: addrStr.address || '',
        lat: addrStr.latitude != null ? addrStr.latitude : (addrStr.lat || null),
        lng: addrStr.longitude != null ? addrStr.longitude : (addrStr.lng || null)
      }
    }
    const s = String(addrStr)
    try {
      const obj = JSON.parse(s)
      if (obj && typeof obj === 'object') {
        return {
          address: obj.address || '',
          lat: obj.latitude != null ? obj.latitude : (obj.lat || null),
          lng: obj.longitude != null ? obj.longitude : (obj.lng || null)
        }
      }
    } catch (e) {}
    return { address: s, lat: null, lng: null }
  },

  formatDate(dt) {
    if (!dt) return ''
    const s = String(dt).replace('T', ' ')
    return s.length > 16 ? s.slice(0, 16) : s
  },

  async departAndStartReport() {
    const api = app.getApi()
    try {
      await api.track.depart(this.data.orderId)
    } catch (e) {
      console.error('出发状态触发失败', e)
      wx.showToast({ title: (e && e.message) || '出发失败，未开启位置上报', icon: 'none' })
      return false
    }
    this._departed = true
    this.startReport()
    return true
  },

  startReport() {
    this.stopReport()
    this.setData({ failCount: 0 })
    this.reportOnce()
    this._timer = setInterval(() => this.reportOnce(), REPORT_INTERVAL)
  },

  stopReport() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
    this.setData({ reporting: false })
  },

  async reportOnce() {
    // 连续失败次数过多则停止
    if (this.data.failCount >= MAX_FAIL_COUNT) {
      this.stopReport()
      wx.showModal({
        title: '位置上报已暂停',
        content: '位置获取连续失败，请检查定位权限或网络后重试。',
        confirmText: '去设置',
        cancelText: '稍后',
        success: (res) => {
          if (res.confirm) wx.openSetting()
        }
      })
      return
    }
    try {
      const loc = await this.getLocation()
      const api = app.getApi()
      await api.track.report(this.data.orderId, {
        latitude: loc.latitude,
        longitude: loc.longitude,
        lat: loc.latitude,
        lng: loc.longitude,
        speed: loc.speed || 0,
        heading: loc.direction || 0
      })
      const now = new Date()
      const time = this.formatTime(now)
      this.setData({
        currentLat: loc.latitude,
        currentLng: loc.longitude,
        lastReportTime: time,
        reporting: true,
        failCount: 0
      })
    } catch (e) {
      console.error('位置上报失败', e)
      const newFail = this.data.failCount + 1
      this.setData({
        reporting: false,
        failCount: newFail,
        permissionDenied: (e && (e.errMsg || '').indexOf('auth') >= 0) || (e && (e.errMsg || '').indexOf('deny') >= 0)
      })
      // 首次失败提示授权
      if (this.data.permissionDenied) {
        wx.showModal({
          title: '需要定位权限',
          content: '位置上报需要开启定位权限，否则客户无法实时追踪师傅位置。',
          confirmText: '去设置',
          cancelText: '稍后',
          success: (res) => {
            if (res.confirm) wx.openSetting()
          }
        })
      }
    }
  },

  getLocation() {
    return new Promise(function (resolve, reject) {
      wx.getLocation({
        type: 'gcj02',
        success: resolve,
        fail: reject
      })
    })
  },

  formatTime(date) {
    const h = String(date.getHours()).padStart(2, '0')
    const m = String(date.getMinutes()).padStart(2, '0')
    const s = String(date.getSeconds()).padStart(2, '0')
    return h + ':' + m + ':' + s
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  async onArrive() {
    if (!this._departed) {
      wx.showToast({ title: '尚未成功确认出发', icon: 'none' })
      return
    }
    wx.showLoading({ title: '确认到达...' })
    const api = app.getApi()
    try {
      // 到达必须使用本次真实定位；任一位置接口失败都不显示到达成功。
      const loc = await this.getLocation()
      const location = {
        latitude: loc.latitude,
        longitude: loc.longitude,
        lat: loc.latitude,
        lng: loc.longitude,
        speed: loc.speed || 0,
        heading: loc.direction || 0
      }
      await api.track.report(this.data.orderId, location)
      await api.track.arrive(this.data.orderId, location)
      wx.hideLoading()
      wx.showToast({ title: '已确认到达', icon: 'success' })
      this.stopReport()
      setTimeout(function () { wx.navigateBack({ delta: 1 }) }, 1000)
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '确认失败', icon: 'none' })
    }
  },

  onCallCustomer() {
    const phone = this.data.order.userPhone
    const value = String(phone || '').trim()
    if (!value || value.indexOf('*') >= 0 || !/^1[3-9]\d{9}$/.test(value)) {
      wx.showToast({ title: '客户电话未提供或已脱敏', icon: 'none' })
      return
    }
    wx.makePhoneCall({ phoneNumber: value })
  },

  onNavigate() {
    const order = this.data.order
    if (!order.lat || !order.lng) {
      wx.showToast({ title: '暂无服务地点坐标', icon: 'none' })
      return
    }
    wx.openLocation({
      latitude: Number(order.lat),
      longitude: Number(order.lng),
      name: order.serviceName || '服务地点',
      address: order.address || ''
    })
  },

  // 手动重试上报
  onRetryReport() {
    if (this._departed) {
      this.startReport()
      return
    }
    this.departAndStartReport()
  }
})

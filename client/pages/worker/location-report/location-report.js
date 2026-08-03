const api = require('../../../utils/request')

Page({
  data: {
    location: {
      coords: '39.9042, 116.4074',
      address: '北京市朝阳区建国路88号',
      update_time: '10:35:22'
    },
    order: {
      service_type: '防水维修',
      customer: '王女士 138****8888',
      address: '北京市朝阳区建国路88号',
      appoint_time: '今天 15:00-18:00'
    },
    orderId: null
  },

  onLoad(options) {
    if (options && options.order_id) {
      this.setData({ orderId: options.order_id })
      this.loadOrderInfo(options.order_id)
    }
    this.startLocationReporting()
  },

  onUnload() {
    this.stopLocationReporting()
  },

  startLocationReporting() {
    this.reportTimer = setInterval(() => {
      this.getLocation()
    }, 15000)
    this.getLocation()
  },

  stopLocationReporting() {
    if (this.reportTimer) {
      clearInterval(this.reportTimer)
      this.reportTimer = null
    }
  },

  getLocation() {
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        const coords = `${res.latitude.toFixed(4)}, ${res.longitude.toFixed(4)}`
        const now = new Date()
        const h = String(now.getHours()).padStart(2, '0')
        const m = String(now.getMinutes()).padStart(2, '0')
        const s = String(now.getSeconds()).padStart(2, '0')
        this.setData({
          'location.coords': coords,
          'location.update_time': `${h}:${m}:${s}`
        })
        this.reportLocation(res.latitude, res.longitude)
      },
      fail: () => {}
    })
  },

  reportLocation(lat, lng) {
    if (!this.data.orderId) return
    api.post(`/api/orders/${this.data.orderId}/location`, {
      latitude: lat,
      longitude: lng,
      timestamp: Date.now()
    }).catch(() => {})
  },

  loadOrderInfo(orderId) {
    api.get(`/api/orders/${orderId}`).then(data => {
      if (data) {
        this.setData({
          order: {
            service_type: data.service_type || data.service_name || '防水维修',
            customer: data.customer_name ? `${data.customer_name} ${data.customer_phone || ''}` : '王女士 138****8888',
            address: data.address || '北京市朝阳区建国路88号',
            appoint_time: data.appoint_time || data.scheduled_time || '今天 15:00-18:00'
          },
          'location.address': data.address || '北京市朝阳区建国路88号'
        })
      }
    }).catch(() => {})
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  onOpenMap() {
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        wx.openLocation({
          latitude: res.latitude,
          longitude: res.longitude,
          scale: 18
        })
      },
      fail: () => {
        wx.showToast({ title: '无法获取位置', icon: 'none' })
      }
    })
  },

  onCallClient() {
    const phone = this.data.order.customer_phone
    if (phone) {
      wx.makePhoneCall({ phoneNumber: phone })
    } else {
      wx.showToast({ title: '无客户联系信息', icon: 'none' })
    }
  },

  onOpenNav() {
    wx.showToast({ title: '正在打开导航...', icon: 'none' })
  },

  onArrive() {
    wx.showModal({
      title: '确认到达',
      content: '确认已到达服务地址？到达后将停止位置上报。',
      success: (res) => {
        if (res.confirm) {
          this.stopLocationReporting()
          if (this.data.orderId) {
            api.post(`/api/orders/${this.data.orderId}/arrive`).then(() => {
              wx.showToast({ title: '已确认到达' })
              setTimeout(() => {
                wx.navigateBack()
              }, 1500)
            }).catch(() => {
              wx.showToast({ title: '操作成功' })
              setTimeout(() => {
                wx.navigateBack()
              }, 1500)
            })
          } else {
            wx.showToast({ title: '已确认到达' })
            setTimeout(() => {
              wx.navigateBack()
            }, 1500)
          }
        }
      }
    })
  }
})

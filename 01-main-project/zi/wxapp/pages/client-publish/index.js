// pages/client-publish/index.js — 客户端发布订单页
// 三步下单：①选服务类型 ②描述问题 ③确认提交
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { isEmpty } = require('../../utils/validate')

Page({
  data: {
    statusBarHeight: 20,
    step: 1,
    services: [],
    selectedService: null,
    description: '',
    images: [],
    address: null,
    time: '',
    appointTime: '',
    mode: 'bidding',
    urgent: 0,
    modes: [
      { key: 'bidding', name: '竞价模式', desc: '多师傅报价，选最优' },
      { key: 'fixed', name: '一口价', desc: '定价发布，先到先得' },
      { key: 'bounty', name: '悬赏模式', desc: '加急悬赏，快速响应' }
    ],
    urgentOptions: [
      { value: 0, label: '不加急' },
      { value: 10, label: '+¥10' },
      { value: 20, label: '+¥20' },
      { value: 50, label: '+¥50' }
    ],
    icons: {},
    submitting: false
  },

  onLoad(query) {
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        location: buildIcon('location', COLORS.brand),
        calendar: buildIcon('calendar', COLORS.brand),
        camera: buildIcon('camera', COLORS.text3),
        check: buildIcon('check', '#FFFFFF'),
        arrowRight: buildIcon('arrowRight', COLORS.text3)
      }
    })
    this.loadServices(query && query.serviceKey)
  },

  onShow() {
    // 角色可能切换，刷新 tab
    const tb = this.selectComponent('#tabbar')
    if (tb) tb.refresh()
  },

  async loadServices(serviceKey) {
    const api = app.getApi()
    try {
      const services = await api.getServices()
      const servicesWithIcons = services.map(s => ({
        ...s,
        iconUrl: buildIcon(s.icon, COLORS.brand)
      }))
      this.setData({ services: servicesWithIcons })
      // 接收 query 参数自动选中服务，并进入第二步
      if (serviceKey) {
        const target = servicesWithIcons.find(s => s.key === serviceKey)
        if (target) {
          this.setData({ selectedService: target, step: 2 })
        }
      }
    } catch (e) {
      console.error('加载服务失败', e)
    }
  },

  // 选中服务
  onServiceSelect(e) {
    const key = e.currentTarget.dataset.key
    const target = this.data.services.find(s => s.key === key)
    if (target) this.setData({ selectedService: target })
  },

  // 下一步
  onStepNext() {
    if (this.data.step === 1 && !this.data.selectedService) {
      wx.showToast({ title: '请先选择服务类型', icon: 'none' })
      return
    }
    if (this.data.step === 2) {
      if (!this.data.description) {
        wx.showToast({ title: '请描述问题', icon: 'none' })
        return
      }
      if (!this.data.address) {
        wx.showToast({ title: '请选择服务地址', icon: 'none' })
        return
      }
      if (!this.data.time) {
        wx.showToast({ title: '请选择上门时间', icon: 'none' })
        return
      }
    }
    this.setData({ step: Math.min(3, this.data.step + 1) })
  },

  // 上一步
  onStepPrev() {
    if (this.data.step === 1) return
    this.setData({ step: Math.max(1, this.data.step - 1) })
  },

  // 描述输入
  onDescInput(e) {
    this.setData({ description: e.detail.value })
  },

  // 选择图片
  onChooseImage() {
    const remain = 3 - this.data.images.length
    if (remain <= 0) {
      wx.showToast({ title: '最多上传3张', icon: 'none' })
      return
    }
    if (wx.chooseMedia) {
      wx.chooseMedia({
        count: remain,
        mediaType: ['image'],
        sourceType: ['album', 'camera'],
        success: (res) => {
          const newImgs = res.tempFiles.map(f => f.tempFilePath)
          this.setData({ images: this.data.images.concat(newImgs) })
        },
        fail: () => {
          if (app.globalData.useMock) {
            const placeholder = 'mock_img_' + Date.now()
            this.setData({ images: this.data.images.concat([placeholder]) })
          }
        }
      })
    } else if (app.globalData.useMock) {
      const placeholder = 'mock_img_' + Date.now()
      this.setData({ images: this.data.images.concat([placeholder]) })
    } else {
      wx.showToast({ title: '当前微信版本不支持选图', icon: 'none' })
    }
  },

  // 删除图片
  onRemoveImage(e) {
    const idx = e.currentTarget.dataset.index
    const images = this.data.images.slice()
    images.splice(idx, 1)
    this.setData({ images })
  },

  // 选择地址
  onChooseLocation() {
    // 优先使用微信选点；取消选点时再读取账号内已保存的真实地址。
    wx.chooseLocation({
      success: (res) => {
        this.setData({
          address: {
            name: res.name || '当前位置',
            detail: [res.address, res.name].filter(Boolean).join(' '),
            lat: res.latitude,
            lng: res.longitude
          }
        })
      },
      fail: () => {
        const api = app.getApi()
        api.getAddresses().then(addrs => {
          const address = (addrs || []).find(item => item.is_default) || (addrs || [])[0]
          if (address) {
            this.setData({
              address: Object.assign({}, address, {
                lat: address.location_lat != null ? address.location_lat : address.lat,
                lng: address.location_lng != null ? address.location_lng : address.lng
              })
            })
          } else {
            wx.showToast({ title: '请先添加服务地址', icon: 'none' })
          }
        }).catch(error => console.error('读取已保存地址失败', error))
      }
    })
  },

  // 选择时间
  onChooseTime() {
    const now = new Date()
    const definitions = [
      { dayOffset: 0, startHour: 15, label: '今天 15:00-18:00' },
      { dayOffset: 1, startHour: 9, label: '明天 09:00-12:00' },
      { dayOffset: 1, startHour: 14, label: '明天 14:00-18:00' },
      { dayOffset: 2, startHour: 9, label: '后天 09:00-12:00' }
    ]
    const slots = definitions.map(item => {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() + item.dayOffset, item.startHour, 0, 0, 0)
      return Object.assign({}, item, { start })
    }).filter(item => item.start.getTime() > now.getTime())
    const times = slots.map(item => item.label)
    if (!times.length) {
      wx.showToast({ title: '暂无可预约时段', icon: 'none' })
      return
    }
    wx.showActionSheet({
      itemList: times,
      success: (res) => {
        const slot = slots[res.tapIndex]
        this.setData({ time: slot.label, appointTime: slot.start.toISOString() })
      }
    })
  },

  // 选择下单模式
  onModeSelect(e) {
    const mode = e.currentTarget.dataset.key
    if (mode !== 'bidding') {
      wx.showToast({ title: '当前仅开放竞价模式', icon: 'none' })
      return
    }
    this.setData({ mode })
  },

  async uploadOrderImages(api) {
    if (app.globalData.useMock) return this.data.images.slice()
    const uploaded = []
    for (const filePath of this.data.images) {
      if (/^https:\/\//i.test(filePath)) {
        uploaded.push(filePath)
        continue
      }
      const result = await api.upload.image(filePath)
      if (!result || !result.url) throw new Error('图片上传响应缺少 URL')
      uploaded.push(result.url)
    }
    return uploaded
  },

  // 选择加急
  onUrgentSelect(e) {
    this.setData({ urgent: Number(e.currentTarget.dataset.value) })
  },

  // 提交订单
  async onSubmit() {
    if (this.data.submitting) return  // 防重复提交
    if (!this.data.selectedService) {
      wx.showToast({ title: '请选择服务', icon: 'none' })
      return
    }
    if (isEmpty(this.data.description)) {
      wx.showToast({ title: '请描述问题', icon: 'none' })
      return
    }
    if (!this.data.address) {
      wx.showToast({ title: '请选择地址', icon: 'none' })
      return
    }
    if (isEmpty(this.data.time)) {
      wx.showToast({ title: '请选择时间', icon: 'none' })
      return
    }
    // 描述长度限制（防超长文本攻击）
    if (this.data.description.length > 500) {
      wx.showToast({ title: '描述不超过 500 字', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    const api = app.getApi()
    let submitted = false
    try {
      // 后端 CreateOrderRequest 字段为 snake_case 且 extra=forbid：
      // service_type / address(object) / appoint_time / urgent(bool) / urgent_amount
      // 前端 serviceKey/time/urgent(number) 必须重映射，否则 422
      const addr = this.data.address
      const addressStr = addr ? String(addr.detail || addr.name || '').trim() : ''
      const lat = addr && (addr.location_lat != null ? addr.location_lat : addr.lat)
      const lng = addr && (addr.location_lng != null ? addr.location_lng : addr.lng)
      const latitude = Number(lat)
      const longitude = Number(lng)
      if (!addressStr || !Number.isFinite(latitude) || !Number.isFinite(longitude) ||
          latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180 ||
          (latitude === 0 && longitude === 0)) {
        wx.showToast({ title: '请选择有效服务地址', icon: 'none' })
        return
      }
      const structuredAddress = {
        address: addressStr,
        latitude,
        longitude
      }
      const urgentAmount = Number(this.data.urgent) || 0
      wx.showLoading({ title: this.data.images.length ? '上传并发布' : '正在发布', mask: true })
      const imageUrls = await this.uploadOrderImages(api)
      await api.orders.create({
        service_type: this.data.selectedService.key,
        description: this.data.description.trim(),
        images: imageUrls,
        address: structuredAddress,
        appoint_time: this.data.appointTime,
        budget: 0,
        urgent: urgentAmount > 0,
        urgent_amount: urgentAmount
      })
      submitted = true
      wx.hideLoading()
      wx.showToast({ title: '发布成功', icon: 'success' })
      setTimeout(() => {
        wx.redirectTo({ url: '/pages/client-orders/index' })
      }, 1200)
    } catch (e) {
      wx.hideLoading()
      console.error('订单发布失败', e)
      wx.showToast({ title: (e && e.message) || '发布失败', icon: 'none' })
    } finally {
      if (!submitted) this.setData({ submitting: false })
    }
  }
})

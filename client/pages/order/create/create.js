const api = require('../../../utils/request')

Page({
  data: {
    serviceKey: '',
    workerId: null,
    service: null,
    workers: [],
    selectedWorker: null,
    form: {
      address_id: null,
      address: '',
      address_text: '',
      latitude: null,
      longitude: null,
      phone: '',
      contact_name: '',
      appoint_date: '',
      appoint_time: '',
      remark: '',
      description: '',
      images: [],
      urgent: false,
      urgent_amount: 0,
      insurance_level: '',
      insurance_amount: 0,
      coupon_id: null
    },
    dateList: [],
    timeList: ['09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00'],
    coupons: [],
    selectedCoupon: null,
    urgentOptions: [
      { label: '不加急', value: 0 },
      { label: '+10元', value: 10 },
      { label: '+20元', value: 20 },
      { label: '+50元', value: 50 }
    ],
    insuranceOptions: [
      { label: '基础版', value: 'basic', amount: 3, desc: '3元' },
      { label: '标准版', value: 'standard', amount: 5, desc: '5元' },
      { label: '高级版', value: 'premium', amount: 10, desc: '10元' }
    ],
    estimatedTotal: 0
  },
  onLoad(options) {
    const { service_type, worker_id, key } = options
    const serviceKey = service_type || key || 'electric'
    this.setData({ serviceKey, workerId: worker_id || null })
    this.loadService(serviceKey)
    this.loadDates()
    if (worker_id) this.loadWorkers(worker_id)
  },
  loadService(key) {
    api.get(`/api/services/${key}`).then(data => {
      this.setData({ service: data })
      this.updateEstimate()
      this.loadCoupons()
    }).catch(() => wx.showToast({ title: '加载失败', icon: 'none' }))
  },
  loadWorkers(workerId) {
    api.get(`/api/reviews/worker/${workerId}/detail`).then(data => {
      this.setData({ workers: [data], selectedWorker: data })
    }).catch(() => {})
  },
  loadDates() {
    const dates = []
    for (let i = 0; i < 7; i++) {
      const d = new Date()
      d.setDate(d.getDate() + i)
      dates.push({
        key: d.toISOString().slice(0, 10),
        label: `${d.getMonth() + 1}/${d.getDate()}`,
        weekday: ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
      })
    }
    this.setData({ dateList: dates })
  },
  selectDate(e) {
    this.setData({ 'form.appoint_date': e.currentTarget.dataset.date })
  },
  selectTime(e) {
    this.setData({ 'form.appoint_time': e.currentTarget.dataset.time })
  },
  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [`form.${field}`]: e.detail.value })
  },
  chooseAddress() {
    this.chooseLocation()
  },
  chooseLocation() {
    wx.chooseLocation({
      success: (res) => {
        // res has: name, address, latitude, longitude
        this.setData({
          'form.address': JSON.stringify({ address: res.address, name: res.name, latitude: res.latitude, longitude: res.longitude }),
          'form.address_text': res.name ? `${res.name} (${res.address})` : res.address,
          'form.latitude': res.latitude,
          'form.longitude': res.longitude
        })
      },
      fail: (err) => {
        if (err && err.errMsg && err.errMsg.indexOf('cancel') === -1) {
          wx.showToast({ title: '选择位置失败', icon: 'none' })
        }
      }
    })
  },
  useCurrentLocation() {
    wx.showLoading({ title: '定位中...' })
    wx.getLocation({
      type: 'gcj02',
      success: (loc) => {
        api.get('/api/map/reverse-geocode', { lat: loc.latitude, lng: loc.longitude }).then(data => {
          wx.hideLoading()
          const name = (data && data.name) || '当前位置'
          const address = (data && data.address) || '当前位置'
          this.setData({
            'form.address': JSON.stringify({ address, name, latitude: loc.latitude, longitude: loc.longitude }),
            'form.address_text': name ? `${name} (${address})` : address,
            'form.latitude': loc.latitude,
            'form.longitude': loc.longitude
          })
        }).catch(() => {
          wx.hideLoading()
          // 逆地理失败也允许保存坐标，仅显示坐标
          this.setData({
            'form.address': JSON.stringify({ address: '当前位置', name: '当前位置', latitude: loc.latitude, longitude: loc.longitude }),
            'form.address_text': `当前位置 (${loc.latitude.toFixed(6)},${loc.longitude.toFixed(6)})`,
            'form.latitude': loc.latitude,
            'form.longitude': loc.longitude
          })
        })
      },
      fail: () => {
        wx.hideLoading()
        wx.showToast({ title: '获取位置失败', icon: 'none' })
      }
    })
  },
  selectWorker(e) {
    const id = e.currentTarget.dataset.id
    const w = this.data.workers.find(x => x.id === id)
    this.setData({ selectedWorker: w })
  },
  onDescriptionInput(e) {
    this.setData({ 'form.description': e.detail.value })
  },
  chooseImage() {
    wx.chooseImage({
      count: 9 - this.data.form.images.length,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        this.uploadImagesToApi(res.tempFilePaths).then(urls => {
          const images = this.data.form.images.concat(urls)
          this.setData({ 'form.images': images })
        }).catch(() => wx.showToast({ title: '图片上传失败', icon: 'none' }))
      }
    })
  },
  uploadImagesToApi(tempFilePaths) {
    const app = getApp()
    const baseURL = app.globalData.baseURL || 'http://localhost:8000'
    const token = app.globalData.token
    const uploads = tempFilePaths.map(path => {
      return new Promise((resolve, reject) => {
        wx.uploadFile({
          url: `${baseURL}/api/upload/image`,
          filePath: path,
          name: 'file',
          header: token ? { 'Authorization': `Bearer ${token}` } : {},
          success: (res) => {
            if (res.statusCode >= 200 && res.statusCode < 300) {
              try {
                const body = JSON.parse(res.data)
                if (body.code === 0 || body.code === 200) {
                  resolve(body.data.url || body.data)
                } else {
                  reject(body)
                }
              } catch (e) {
                reject(e)
              }
            } else {
              reject(res)
            }
          },
          fail: reject
        })
      })
    })
    return Promise.all(uploads)
  },
  removeImage(e) {
    const idx = e.currentTarget.dataset.idx
    const images = this.data.form.images.slice()
    images.splice(idx, 1)
    this.setData({ 'form.images': images })
  },
  selectUrgent(e) {
    const value = e.currentTarget.dataset.value
    this.setData({
      'form.urgent': value > 0,
      'form.urgent_amount': value
    }, () => this.updateEstimate())
  },
  selectInsurance(e) {
    const item = e.currentTarget.dataset.item
    this.setData({
      'form.insurance_level': item.value,
      'form.insurance_amount': item.amount
    }, () => this.updateEstimate())
  },
  loadCoupons() {
    const { service } = this.data
    if (!service || !service.price_min) return
    api.get('/api/coupons/available', { amount: service.price_min }).then(data => {
      this.setData({ coupons: data || [] })
    }).catch(() => {})
  },
  selectCoupon(e) {
    const id = e.currentTarget.dataset.id
    const coupon = this.data.coupons.find(c => c.id === id)
    this.setData({
      'form.coupon_id': id,
      selectedCoupon: coupon || null
    })
  },
  updateEstimate() {
    const { service, form } = this.data
    const base = service ? (service.price_min || 0) : 0
    const total = base + (form.urgent_amount || 0) + (form.insurance_amount || 0)
    this.setData({ estimatedTotal: total })
  },
  submitOrder() {
    const { form, serviceKey, selectedWorker } = this.data
    if (!form.address_text) { wx.showToast({ title: '请填写地址', icon: 'none' }); return }
    if (!form.contact_name) { wx.showToast({ title: '请填写联系人', icon: 'none' }); return }
    if (!form.phone) { wx.showToast({ title: '请填写电话', icon: 'none' }); return }
    if (!form.appoint_date) { wx.showToast({ title: '请选择预约日期', icon: 'none' }); return }

    // 优先使用结构化 address（含坐标）；若用户手动编辑过 address_text 但未选点，则回填
    let addressPayload = form.address
    if (!addressPayload && form.address_text) {
      addressPayload = JSON.stringify({ address: form.address_text, name: '', latitude: null, longitude: null })
    }

    const payload = {
      service_type: serviceKey,
      address: addressPayload,
      contact_name: form.contact_name,
      contact_phone: form.phone,
      appoint_time: `${form.appoint_date} ${form.appoint_time || ''}`,
      remark: form.remark,
      description: form.description,
      images: form.images,
      urgent_amount: form.urgent_amount,
      insurance_level: form.insurance_level,
      insurance_amount: form.insurance_amount,
      coupon_id: form.coupon_id
    }
    if (form.latitude) payload.latitude = form.latitude
    if (form.longitude) payload.longitude = form.longitude
    if (selectedWorker) payload.worker_id = selectedWorker.id

    api.post('/api/orders', payload).then(data => {
      wx.redirectTo({ url: `/pages/order/detail/detail?id=${data.id}` })
    }).catch(() => wx.showToast({ title: '下单失败', icon: 'none' }))
  }
})

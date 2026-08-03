Page({
  data: {
    selectedService: 'waterproof',
    description: '',
    descLength: 0,
    address: '',
    timeSlot: '',
    tag: '',
    mode: 'bid'
  },

  pickService(e) {
    this.setData({ selectedService: e.currentTarget.dataset.key })
  },

  onDescInput(e) {
    const val = e.detail.value
    this.setData({ description: val, descLength: val.length })
  },

  onPickAddress() {
    wx.chooseLocation({
      success: (res) => {
        this.setData({ address: `${res.name} ${res.address}` })
      },
      fail: () => {
        this.setData({ address: '浙江省杭州市西湖区文三路 123 号' })
      }
    })
  },

  onPickTime() {
    const now = new Date()
    const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000)
    const day = tomorrow.getMonth() + 1
    const date = tomorrow.getDate()
    const slots = ['上午 9:00-12:00', '下午 14:00-18:00', '晚上 18:00-21:00']
    wx.showActionSheet({
      itemList: slots,
      success: (res) => {
        this.setData({ timeSlot: `${day}月${date}日 ${slots[res.tapIndex]}` })
      }
    })
  },

  pickTag(e) {
    const t = e.currentTarget.dataset.tag
    this.setData({ tag: this.data.tag === t ? '' : t })
  },

  pickMode(e) {
    this.setData({ mode: e.currentTarget.dataset.mode })
  },

  onSubmit() {
    if (!this.data.description || this.data.description.length < 10) {
      wx.showToast({ title: '请详细描述问题（至少10字）', icon: 'none' })
      return
    }
    if (!this.data.address) {
      wx.showToast({ title: '请选择地址', icon: 'none' })
      return
    }
    if (!this.data.timeSlot) {
      wx.showToast({ title: '请选择预约时间', icon: 'none' })
      return
    }
    wx.showLoading({ title: '发布中...' })
    setTimeout(() => {
      wx.hideLoading()
      wx.showToast({ title: '发布成功', icon: 'success' })
      setTimeout(() => {
        wx.switchTab({ url: '/pages/index/index' })
      }, 1500)
    }, 1200)
  },

  onClose() {
    wx.navigateBack()
  },

  goHome() {
    wx.switchTab({ url: '/pages/index/index' })
  },

  goOrders() {
    wx.navigateTo({ url: '/pages/orders/list/list' })
  },

  goMine() {
    wx.switchTab({ url: '/pages/mine/mine' })
  }
})

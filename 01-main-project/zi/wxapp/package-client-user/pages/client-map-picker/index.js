const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

function finite(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function safeText(value) {
  return String(value || '').trim()
}

const designPage = createDesignPage({
  pageId: 'page-client-map-picker',
  route: 'pages/client-map-picker/index',
  source: 'pages/client-map-picker.html',
  sourceHash: 'fnv1a-8d4de054',
  title: '地图选点'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    query: '',
    city: '',
    selected: false,
    latitude: null,
    longitude: null,
    title: '尚未选择位置',
    detail: '可搜索地址或使用微信地图选点',
    sourceText: '尚未选点',
    selection: null,
    searching: false,
    locating: false
  }),

  onLoad(options) {
    const query = options || {}
    const latitude = finite(query.latitude != null ? query.latitude : query.lat)
    const longitude = finite(query.longitude != null ? query.longitude : query.lng)
    const address = safeText(query.address)
    this.setData({ query: address, city: safeText(query.city) })
    if (latitude !== null && longitude !== null) {
      this.applySelection({ latitude, longitude, address, name: address }, '已载入原地址坐标')
    }
  },

  onQueryInput(event) {
    this.setData({ query: String(event.detail.value || '').slice(0, 100) })
  },

  async onSearch() {
    if (this.data.searching) return
    const query = safeText(this.data.query)
    if (!query) {
      wx.showToast({ title: '请输入要搜索的地址', icon: 'none' })
      return
    }
    const api = app.getApi && app.getApi()
    if (!api || !api.map || !api.map.geocode) {
      wx.showToast({ title: '地址解析接口不可用', icon: 'none' })
      return
    }
    this.setData({ searching: true })
    wx.showLoading({ title: '解析地址', mask: true })
    try {
      const result = await api.map.geocode(query, this.data.city)
      const location = result && result.location || result || {}
      const latitude = finite(location.lat != null ? location.lat : location.latitude)
      const longitude = finite(location.lng != null ? location.lng : location.longitude)
      if (latitude === null || longitude === null) {
        throw new Error(result && result.message || '没有解析到可用坐标')
      }
      this.applySelection(Object.assign({}, result, { latitude, longitude, address: result.address || query, name: result.name || query }), '后端地址解析')
    } catch (error) {
      console.error('[地图选点] 地址解析失败', error)
      if (error && (error.message === '没有解析到可用坐标' || error.message && error.message.indexOf('地图') >= 0)) {
        wx.showToast({ title: error.message, icon: 'none' })
      }
    } finally {
      wx.hideLoading()
      this.setData({ searching: false })
    }
  },

  chooseLocation() {
    return new Promise((resolve, reject) => wx.chooseLocation({ success: resolve, fail: reject }))
  },

  async onLocate() {
    if (this.data.locating) return
    this.setData({ locating: true })
    try {
      const nativeLocation = await this.chooseLocation()
      const latitude = finite(nativeLocation && nativeLocation.latitude)
      const longitude = finite(nativeLocation && nativeLocation.longitude)
      if (latitude === null || longitude === null) throw new Error('微信地图未返回可用坐标')
      let geocode = {}
      const api = app.getApi && app.getApi()
      if (api && api.map && api.map.reverseGeocode) {
        try { geocode = await api.map.reverseGeocode(latitude, longitude) || {} } catch (error) {
          console.warn('[地图选点] 逆地址解析不可用，保留微信选点结果', error)
        }
      }
      this.applySelection(Object.assign({}, geocode, {
        latitude,
        longitude,
        name: nativeLocation.name || geocode.name,
        address: geocode.address || nativeLocation.address || nativeLocation.name
      }), '微信地图选点')
    } catch (error) {
      if (!error || String(error.errMsg || '').indexOf('cancel') < 0) {
        console.error('[地图选点] 微信地图选点失败', error)
        wx.showToast({ title: error && error.message || '暂时无法选择位置', icon: 'none' })
      }
    } finally {
      this.setData({ locating: false })
    }
  },

  applySelection(value, sourceText) {
    const latitude = finite(value && (value.latitude != null ? value.latitude : value.lat))
    const longitude = finite(value && (value.longitude != null ? value.longitude : value.lng))
    if (latitude === null || longitude === null) return false
    const title = safeText(value.name || value.address) || '已选择位置'
    const detail = safeText(value.address || value.name) || (latitude.toFixed(6) + ', ' + longitude.toFixed(6))
    const selection = {
      latitude,
      longitude,
      name: title,
      address: detail,
      province: safeText(value.province),
      city: safeText(value.city),
      district: safeText(value.district)
    }
    this.setData({ selected: true, latitude, longitude, title, detail, sourceText, selection, query: this.data.query || title })
    return true
  },

  onConfirm() {
    if (!this.data.selected || !this.data.selection) {
      wx.showToast({ title: '请先选择真实位置', icon: 'none' })
      return
    }
    const pages = getCurrentPages()
    const previous = pages[pages.length - 2]
    if (!previous || typeof previous.applyMapSelection !== 'function') {
      wx.showToast({ title: '返回页不支持位置回填，本次未保存', icon: 'none' })
      return
    }
    const accepted = previous.applyMapSelection(Object.assign({}, this.data.selection))
    if (accepted === false) {
      wx.showToast({ title: '返回页未接受该位置，本次未保存', icon: 'none' })
      return
    }
    wx.navigateBack({ delta: 1 })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/package-client/pages/client-address-edit/index' }) })
  }
}))

const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

function listOf(value) {
  if (Array.isArray(value)) return value
  if (value && Array.isArray(value.items)) return value.items
  if (value && Array.isArray(value.list)) return value.list
  return []
}

function finite(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

const designPage = createDesignPage({
  pageId: 'page-client-address-edit',
  route: 'pages/client-address-edit/index',
  source: 'pages/client-address-edit.html',
  sourceHash: 'fnv1a-43228497',
  title: '新增地址'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    addressId: '',
    pageTitle: '新增地址',
    name: '',
    phone: '',
    region: [],
    regionText: '请选择省 / 市 / 区',
    detail: '',
    label: '家',
    isDefault: false,
    latitude: null,
    longitude: null,
    mapAddress: '',
    mapSelected: false,
    formReady: false,
    loading: true,
    saving: false,
    unsupportedMode: false
  }),

  async onLoad(options) {
    const query = options || {}
    const mode = String(query.mode || '').trim()
    if (mode && mode !== 'client' && mode !== 'address') {
      this.setData({ unsupportedMode: true, loading: false, pageTitle: '地址编辑' })
      return
    }
    const addressId = String(query.id || query.addressId || '').trim()
    this.setData({ addressId, pageTitle: addressId ? '编辑地址' : '新增地址' })
    if (addressId) await this.loadAddress(addressId)
    else await this.prefillAccount()
  },

  async prefillAccount() {
    try {
      const user = await app.getApi().auth.me()
      this.setData({
        name: String(user && (user.nickname || user.name) || ''),
        phone: String(user && user.phone || ''),
        loading: false
      })
    } catch (error) {
      console.error('[地址编辑] 预填账号信息失败', error)
      this.setData({ loading: false })
    }
    this.updateReady()
  },

  async loadAddress(addressId) {
    try {
      const result = await app.getApi().auth.getAddresses()
      const address = listOf(result).find(item => String(item && item.id) === String(addressId))
      if (!address) throw new Error('未找到要编辑的地址')
      const region = [address.province, address.city, address.district].map(value => String(value || '')).filter(Boolean)
      const latitude = finite(address.location_lat != null ? address.location_lat : address.lat)
      const longitude = finite(address.location_lng != null ? address.location_lng : address.lng)
      this.setData({
        name: String(address.name || ''),
        phone: String(address.phone || ''),
        region,
        regionText: region.length ? region.join(' / ') : '请选择省 / 市 / 区',
        detail: String(address.detail || ''),
        label: String(address.label || address.tag || '家'),
        isDefault: !!(address.is_default != null ? address.is_default : address.isDefault),
        latitude,
        longitude,
        mapAddress: String(address.detail || ''),
        mapSelected: latitude !== null && longitude !== null,
        loading: false
      })
      this.updateReady()
    } catch (error) {
      console.error('[地址编辑] 加载地址失败', error)
      this.setData({ loading: false, saving: false })
      wx.showModal({
        title: '无法编辑地址',
        content: error && error.message || '地址不存在或暂时无法读取',
        showCancel: false,
        success: () => this.onBack()
      })
    }
  },

  onFieldInput(event) {
    const field = String(event.currentTarget.dataset.field || '')
    if (['name', 'phone', 'detail'].indexOf(field) < 0) return
    let value = String(event.detail.value || '')
    if (field === 'phone') value = value.replace(/\D/g, '').slice(0, 11)
    this.setData({ [field]: value }, () => this.updateReady())
  },

  onRegionChange(event) {
    const region = Array.isArray(event.detail.value) ? event.detail.value : []
    this.setData({ region, regionText: region.length ? region.join(' / ') : '请选择省 / 市 / 区' }, () => this.updateReady())
  },

  onToggleDefault() {
    if (this.data.unsupportedMode) return
    this.setData({ isDefault: !this.data.isDefault })
  },

  updateReady() {
    const ready = !!(
      String(this.data.name || '').trim() &&
      /^1[3-9]\d{9}$/.test(String(this.data.phone || '').trim()) &&
      Array.isArray(this.data.region) && this.data.region.length === 3 &&
      String(this.data.detail || '').trim()
    )
    this.setData({ formReady: ready })
  },

  onOpenMap() {
    if (this.data.unsupportedMode) {
      this.onUnsupportedMode()
      return
    }
    const params = []
    if (this.data.mapSelected) {
      params.push('latitude=' + encodeURIComponent(String(this.data.latitude)))
      params.push('longitude=' + encodeURIComponent(String(this.data.longitude)))
      params.push('address=' + encodeURIComponent(this.data.mapAddress || this.data.detail || ''))
    }
    if (this.data.region && this.data.region[1]) params.push('city=' + encodeURIComponent(this.data.region[1]))
    wx.navigateTo({
      url: '/package-client/pages/client-map-picker/index' + (params.length ? '?' + params.join('&') : ''),
      fail: () => wx.showToast({ title: '地图选点页暂不可用', icon: 'none' })
    })
  },

  applyMapSelection(selection) {
    const value = selection || {}
    const latitude = finite(value.latitude != null ? value.latitude : value.lat)
    const longitude = finite(value.longitude != null ? value.longitude : value.lng)
    if (latitude === null || longitude === null) return false
    const address = String(value.address || value.name || '').trim()
    const selectedRegion = [value.province, value.city, value.district].map(item => String(item || '')).filter(Boolean)
    const changes = {
      latitude,
      longitude,
      mapSelected: true,
      mapAddress: address || '已选择地图位置'
    }
    if (!String(this.data.detail || '').trim() && address) changes.detail = address
    if (selectedRegion.length === 3) {
      changes.region = selectedRegion
      changes.regionText = selectedRegion.join(' / ')
    }
    this.setData(changes, () => this.updateReady())
    return true
  },

  async onSave() {
    if (this.data.unsupportedMode) {
      this.onUnsupportedMode()
      return
    }
    if (this.data.saving || this.data.loading) return
    this.updateReady()
    if (!this.data.formReady) {
      wx.showToast({ title: '请完整填写姓名、手机号、地区和详细地址', icon: 'none' })
      return
    }
    const region = this.data.region
    const payload = {
      name: String(this.data.name).trim(),
      phone: String(this.data.phone).trim(),
      province: region[0],
      city: region[1],
      district: region[2],
      detail: String(this.data.detail).trim(),
      label: this.data.label || '家',
      is_default: !!this.data.isDefault
    }
    if (this.data.mapSelected) {
      payload.location_lat = this.data.latitude
      payload.location_lng = this.data.longitude
    }
    this.setData({ saving: true })
    try {
      const api = app.getApi()
      if (this.data.addressId) await api.auth.updateAddress(this.data.addressId, payload)
      else await api.auth.addAddress(payload)
      wx.showToast({ title: this.data.addressId ? '地址已更新' : '地址已添加', icon: 'success' })
      setTimeout(() => {
        wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/address/index' }) })
      }, 500)
    } catch (error) {
      console.error('[地址编辑] 保存地址失败', error)
    } finally {
      this.setData({ saving: false })
    }
  },

  onUnsupportedMode() {
    wx.showToast({ title: '当前页面仅支持用户地址；师傅服务区域接口未开放', icon: 'none' })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/address/index' }) })
  }
}))

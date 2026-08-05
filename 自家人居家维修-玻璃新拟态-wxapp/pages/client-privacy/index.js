const { createDesignPage } = require('../../utils/design-page-runtime')

const SAFE_CACHE_KEYS = ['searchHistory', 'addressList', 'client_chat_history']

function permissionState(value) {
  if (value === true) return { text: '已授权', active: true }
  if (value === false) return { text: '已拒绝', active: false }
  return { text: '未请求', active: false }
}

function storageText(kb) {
  const value = Number(kb)
  if (!Number.isFinite(value) || value < 0) return '—'
  if (value < 1024) return value.toFixed(value < 10 ? 1 : 0) + ' KB'
  return (value / 1024).toFixed(2) + ' MB'
}

const designPage = createDesignPage({
  pageId: 'page-client-privacy',
  route: 'pages/client-privacy/index',
  source: 'pages/client-privacy.html',
  sourceHash: 'fnv1a-b7af66bd',
  title: '隐私设置'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    locationText: '读取中',
    locationActive: false,
    cameraText: '读取中',
    cameraActive: false,
    permissionCount: 0,
    storageSizeText: '读取中',
    refreshing: false
  }),

  onShow() {
    this.refreshState(false)
  },

  getSetting() {
    return new Promise((resolve, reject) => wx.getSetting({ success: resolve, fail: reject }))
  },

  async refreshState(showResult) {
    if (this.data.refreshing) return
    this.setData({ refreshing: true })
    try {
      const result = await this.getSetting()
      const auth = result && result.authSetting || {}
      const location = permissionState(auth['scope.userLocation'])
      const camera = permissionState(auth['scope.camera'])
      let storage = {}
      try { storage = wx.getStorageInfoSync ? (wx.getStorageInfoSync() || {}) : {} } catch (error) {}
      this.setData({
        locationText: location.text,
        locationActive: location.active,
        cameraText: camera.text,
        cameraActive: camera.active,
        permissionCount: Number(location.active) + Number(camera.active),
        storageSizeText: storageText(storage.currentSize)
      })
      if (showResult) wx.showToast({ title: '权限状态已刷新', icon: 'success' })
    } catch (error) {
      console.error('[隐私设置] 读取微信权限失败', error)
      this.setData({ locationText: '读取失败', cameraText: '读取失败' })
    } finally {
      this.setData({ refreshing: false })
    }
  },

  onOpenSystemSettings() {
    wx.openSetting({
      success: () => this.refreshState(false),
      fail: error => {
        console.error('[隐私设置] 打开微信设置失败', error)
        wx.showToast({ title: '暂时无法打开微信设置', icon: 'none' })
      }
    })
  },

  onContactsUnavailable() {
    wx.showToast({ title: '小程序未申请通用通讯录权限', icon: 'none' })
  },

  onServerSettingUnavailable() {
    wx.showToast({ title: '服务端隐私偏好接口尚未开放', icon: 'none' })
  },

  onClearCache() {
    let storage = {}
    try { storage = wx.getStorageInfoSync ? (wx.getStorageInfoSync() || {}) : {} } catch (error) {}
    const currentKeys = Array.isArray(storage.keys) ? storage.keys : []
    const targets = SAFE_CACHE_KEYS.filter(key => currentKeys.indexOf(key) >= 0)
    if (!targets.length) {
      wx.showToast({ title: '没有可安全清理的登记缓存', icon: 'none' })
      return
    }
    wx.showModal({
      title: '清除本地缓存',
      content: '将移除搜索、地址列表与在线客服聊天缓存，不会删除 token、账号或订单数据。',
      confirmText: '确认清除',
      success: result => {
        if (!result.confirm) return
        try {
          targets.forEach(key => wx.removeStorageSync(key))
          let next = {}
          try { next = wx.getStorageInfoSync ? (wx.getStorageInfoSync() || {}) : {} } catch (error) {}
          this.setData({ storageSizeText: storageText(next.currentSize) })
          wx.showToast({ title: '登记缓存已清除', icon: 'success' })
        } catch (error) {
          console.error('[隐私设置] 清理登记缓存失败', error)
          wx.showToast({ title: '缓存清理失败', icon: 'none' })
        }
      }
    })
  },

  onRefresh() {
    return this.refreshState(true)
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-settings/index' }) })
  }
}))

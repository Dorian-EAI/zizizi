const { createDesignPage } = require('../../utils/design-page-runtime')

const designPage = createDesignPage({
  pageId: 'page-client-device-management',
  route: 'pages/client-device-management/index',
  source: 'pages/client-device-management.html',
  sourceHash: 'fnv1a-f32c3503',
  title: '登录设备管理'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    deviceName: '正在读取本机信息',
    deviceMeta: '这不是服务端登录会话记录'
  }),

  onLoad() {
    let info = {}
    try {
      if (wx.getDeviceInfo) info = wx.getDeviceInfo() || {}
      else if (wx.getSystemInfoSync) info = wx.getSystemInfoSync() || {}
    } catch (error) {
      console.warn('[登录设备] 读取本机运行环境失败', error)
    }
    const model = String(info.model || '').trim()
    const platform = String(info.platform || info.system || '').trim()
    this.setData({
      deviceName: model || '本机运行环境',
      deviceMeta: (platform ? platform + ' · ' : '') + '仅由微信本机 API 读取，非登录会话'
    })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-account-security/index' }) })
  },

  onUnsupported() {
    wx.showToast({ title: '服务端尚未提供登录设备管理接口', icon: 'none' })
  }
}))

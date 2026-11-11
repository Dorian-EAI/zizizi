const { createDesignPage } = require('../../utils/design-page-runtime')

const designPage = createDesignPage({
  pageId: 'page-client-verification',
  route: 'pages/client-verification/index',
  source: 'pages/client-verification.html',
  sourceHash: 'fnv1a-d93fbf95',
  title: '实名认证'
})

Page(Object.assign(designPage, {
  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/package-client/pages/client-account-security/index' }) })
  },

  onUnsupported() {
    wx.showToast({ title: '用户实名认证接口尚未开放', icon: 'none' })
  }
}))

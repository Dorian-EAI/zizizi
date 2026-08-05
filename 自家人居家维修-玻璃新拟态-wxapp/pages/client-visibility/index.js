const { createDesignPage } = require('../../utils/design-page-runtime')

const designPage = createDesignPage({
  pageId: 'page-client-visibility',
  route: 'pages/client-visibility/index',
  source: 'pages/client-visibility.html',
  sourceHash: 'fnv1a-e0407158',
  title: '信息可见性'
})

Page(Object.assign(designPage, {
  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-privacy/index' }) })
  },

  onUnsupported() {
    wx.showToast({ title: '可见范围设置接口尚未开放', icon: 'none' })
  }
}))

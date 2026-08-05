const { createDesignPage } = require('../../utils/design-page-runtime')

const designPage = createDesignPage({
  pageId: 'page-client-verification-result',
  route: 'pages/client-verification-result/index',
  source: 'pages/client-verification-result.html',
  sourceHash: 'fnv1a-f756ef45',
  title: '认证结果'
})

Page(Object.assign(designPage, {
  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-account-security/index' }) })
  }
}))

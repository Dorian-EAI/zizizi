const { createDesignPage } = require('../../utils/design-page-runtime')

const designPage = createDesignPage({
  pageId: 'page-client-password',
  route: 'pages/client-password/index',
  source: 'pages/client-password.html',
  sourceHash: 'fnv1a-a0f15e7f',
  title: '修改密码'
})

Page(Object.assign(designPage, {
  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-account-security/index' }) })
  },

  onUnsupported() {
    wx.showToast({ title: '用户密码修改接口尚未开放', icon: 'none' })
  }
}))

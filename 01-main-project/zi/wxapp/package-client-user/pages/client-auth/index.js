const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

function maskPhone(value) {
  const phone = String(value || '').replace(/\s+/g, '')
  if (/^1\d{10}$/.test(phone)) return phone.slice(0, 3) + '****' + phone.slice(-4)
  return phone || '尚未绑定手机号'
}

const designPage = createDesignPage({
  pageId: 'page-client-auth',
  route: 'pages/client-auth/index',
  source: 'pages/client-auth.html',
  sourceHash: 'fnv1a-dd6062c9',
  title: '授权管理'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    accountStatus: '待刷新',
    accountCopy: '仅可核验基础账号信息',
    loading: false
  }),

  onLoad() {
    this.refreshAccount(false)
  },

  async refreshAccount(showResult) {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      const api = app.getApi && app.getApi()
      if (!api || !api.auth || !api.auth.me) throw new Error('账号接口不可用')
      const user = await api.auth.me()
      this.setData({
        accountStatus: '基础账号已核验',
        accountCopy: '手机号：' + maskPhone(user && user.phone)
      })
      if (showResult) wx.showToast({ title: '基础账号已刷新', icon: 'success' })
    } catch (error) {
      console.error('[授权管理] 刷新基础账号失败', error)
      this.setData({ accountStatus: '刷新失败', accountCopy: '暂时无法读取基础账号' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onRefresh() {
    return this.refreshAccount(true)
  },

  onUnsupported() {
    wx.showToast({ title: '授权与设备接口尚未开放', icon: 'none' })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/package-client/pages/client-account-security/index' }) })
  }
}))

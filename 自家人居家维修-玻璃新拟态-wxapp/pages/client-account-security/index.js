const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

function maskPhone(value) {
  const phone = String(value || '').replace(/\s+/g, '')
  if (/^1\d{10}$/.test(phone)) return phone.slice(0, 3) + '****' + phone.slice(-4)
  return phone || '尚未绑定'
}

const designPage = createDesignPage({
  pageId: 'page-client-account-security',
  route: 'pages/client-account-security/index',
  source: 'pages/client-account-security.html',
  sourceHash: 'fnv1a-e5eb6a00',
  title: '账号安全'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    phoneText: '正在读取',
    phoneBound: false,
    baseStatus: '待刷新',
    loading: false
  }),

  onLoad() {
    this.loadAccount(false)
  },

  async loadAccount(showResult) {
    if (this.data.loading) return false
    this.setData({ loading: true })
    try {
      const api = app.getApi && app.getApi()
      if (!api || !api.auth || !api.auth.me) throw new Error('账号接口不可用')
      const user = await api.auth.me()
      const phoneBound = !!(user && user.phone)
      this.setData({
        phoneText: maskPhone(user && user.phone),
        phoneBound,
        baseStatus: '基础账号已核验'
      })
      if (showResult) wx.showToast({ title: '基础账号已刷新', icon: 'success' })
      return true
    } catch (error) {
      console.error('[账号安全] 刷新基础账号失败', error)
      this.setData({ baseStatus: '刷新失败', phoneText: '暂时无法读取', phoneBound: false })
      return false
    } finally {
      this.setData({ loading: false })
    }
  },

  onRefresh() {
    return this.loadAccount(true)
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-settings/index' }) })
  }
}))

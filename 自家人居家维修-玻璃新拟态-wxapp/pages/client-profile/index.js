const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

function maskPhone(value) {
  const phone = String(value || '').replace(/\s+/g, '')
  if (/^1\d{10}$/.test(phone)) return phone.slice(0, 3) + '****' + phone.slice(-4)
  return phone || '尚未绑定'
}

function listOf(value) {
  if (Array.isArray(value)) return value
  if (value && Array.isArray(value.items)) return value.items
  if (value && Array.isArray(value.list)) return value.list
  return null
}

const designPage = createDesignPage({
  pageId: 'page-client-profile',
  route: 'pages/client-profile/index',
  source: 'pages/client-profile.html',
  sourceHash: 'fnv1a-dc0a544e',
  title: '个人资料'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    nickname: '正在读取',
    initial: '家',
    avatar: '',
    phoneText: '正在读取',
    memberLevel: '读取中',
    completeness: 0,
    addressCountText: '读取中',
    loading: false
  }),

  onShow() {
    this.loadProfile()
  },

  async loadProfile() {
    if (this.data.loading) return
    this.setData({ loading: true })
    const api = app.getApi && app.getApi()
    if (!api || !api.auth || !api.auth.me) {
      this.setData({ nickname: '账号接口不可用', phoneText: '无法读取', memberLevel: '—', addressCountText: '—', loading: false })
      return
    }

    const userTask = api.auth.me().then(user => ({ ok: true, value: user })).catch(error => ({ ok: false, error }))
    const memberTask = api.member && api.member.detail
      ? api.member.detail().then(value => ({ ok: true, value })).catch(error => ({ ok: false, error }))
      : Promise.resolve({ ok: false })
    const addressTask = api.auth.getAddresses
      ? api.auth.getAddresses().then(value => ({ ok: true, value })).catch(error => ({ ok: false, error }))
      : Promise.resolve({ ok: false })

    const results = await Promise.all([userTask, memberTask, addressTask])
    const userResult = results[0]
    const memberResult = results[1]
    const addressResult = results[2]

    if (userResult.ok) {
      const user = userResult.value || {}
      const nickname = String(user.nickname || user.name || '').trim() || '未设置昵称'
      const avatar = String(user.avatar || user.avatarUrl || '').trim()
      const completed = [nickname !== '未设置昵称', !!avatar, !!user.phone].filter(Boolean).length
      app.globalData.userInfo = user
      try { wx.setStorageSync('userInfo', user) } catch (error) {}
      this.setData({
        nickname,
        initial: nickname.charAt(0) || '家',
        avatar,
        phoneText: maskPhone(user.phone),
        completeness: Math.round(completed / 3 * 100)
      })
    } else {
      console.error('[个人资料] 加载基础账号失败', userResult.error)
      this.setData({ nickname: '加载失败', initial: '家', avatar: '', phoneText: '无法读取', completeness: 0 })
    }

    if (memberResult.ok) {
      const detail = memberResult.value || {}
      const levelInfo = detail.level_info || {}
      this.setData({ memberLevel: levelInfo.level_name || detail.level || '普通会员' })
    } else {
      if (memberResult.error) console.error('[个人资料] 加载会员等级失败', memberResult.error)
      this.setData({ memberLevel: '—' })
    }

    const addresses = addressResult.ok ? listOf(addressResult.value) : null
    if (addresses) this.setData({ addressCountText: addresses.length + ' 个' })
    else {
      if (addressResult.error) console.error('[个人资料] 加载地址数量失败', addressResult.error)
      this.setData({ addressCountText: '—' })
    }
    this.setData({ loading: false })
  },

  onUnsupported() {
    wx.showToast({ title: '该资料字段尚未接入后端', icon: 'none' })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/client-mine/index' }) })
  }
}))

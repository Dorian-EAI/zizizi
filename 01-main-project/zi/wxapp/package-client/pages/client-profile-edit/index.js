const app = getApp()
const { createDesignPage } = require('../../utils/design-page-runtime')

function uploadedUrl(result) {
  if (!result) return ''
  if (typeof result === 'string') return result
  return result.url || result.file_url || (result.data && (result.data.url || result.data.file_url)) || ''
}

const designPage = createDesignPage({
  pageId: 'page-client-profile-edit',
  route: 'pages/client-profile-edit/index',
  source: 'pages/client-profile-edit.html',
  sourceHash: 'fnv1a-0ab42e19',
  title: '编辑资料'
})

Page(Object.assign(designPage, {
  data: Object.assign({}, designPage.data, {
    nickname: '',
    initial: '家',
    avatar: '',
    avatarLocal: '',
    loading: true,
    saving: false
  }),

  onLoad() {
    this.loadProfile()
  },

  async loadProfile() {
    try {
      const user = await app.getApi().auth.me()
      const nickname = String(user && (user.nickname || user.name) || '').trim()
      this.setData({
        nickname,
        initial: nickname.charAt(0) || '家',
        avatar: String(user && (user.avatar || user.avatarUrl) || '').trim(),
        loading: false
      })
    } catch (error) {
      console.error('[编辑资料] 加载资料失败', error)
      this.setData({ loading: false })
    }
  },

  onNicknameInput(event) {
    const nickname = String(event.detail.value || '').slice(0, 30)
    this.setData({ nickname, initial: nickname.trim().charAt(0) || '家' })
  },

  async onChooseAvatar() {
    if (this.data.saving) return
    try {
      let result
      if (wx.chooseMedia) {
        result = await new Promise((resolve, reject) => wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sourceType: ['album', 'camera'],
          sizeType: ['compressed'],
          success: resolve,
          fail: reject
        }))
        const file = result && result.tempFiles && result.tempFiles[0]
        if (file && file.tempFilePath) this.setData({ avatarLocal: file.tempFilePath })
      } else {
        result = await new Promise((resolve, reject) => wx.chooseImage({ count: 1, sizeType: ['compressed'], success: resolve, fail: reject }))
        const path = result && result.tempFilePaths && result.tempFilePaths[0]
        if (path) this.setData({ avatarLocal: path })
      }
    } catch (error) {
      if (!error || String(error.errMsg || '').indexOf('cancel') < 0) {
        console.error('[编辑资料] 选择头像失败', error)
        wx.showToast({ title: '暂时无法选择头像', icon: 'none' })
      }
    }
  },

  async onSave() {
    if (this.data.saving || this.data.loading) return
    const nickname = String(this.data.nickname || '').trim()
    if (!nickname) {
      wx.showToast({ title: '请输入昵称', icon: 'none' })
      return
    }
    this.setData({ saving: true })
    const api = app.getApi()
    let uploaded = ''
    try {
      let avatar = this.data.avatar
      if (this.data.avatarLocal) {
        wx.showLoading({ title: '上传头像', mask: true })
        const result = await api.upload.image(this.data.avatarLocal)
        uploaded = uploadedUrl(result)
        if (!uploaded) throw new Error('上传响应缺少头像地址')
        avatar = uploaded
      }
      wx.showLoading({ title: '保存资料', mask: true })
      const payload = { nickname }
      if (avatar) payload.avatar = avatar
      const response = await api.auth.updateProfile(payload)
      let user = response && response.user ? response.user : response
      if (!user || typeof user !== 'object') user = await api.auth.me()
      app.globalData.userInfo = user
      try { wx.setStorageSync('userInfo', user) } catch (error) {}
      this.setData({ avatar, avatarLocal: '' })
      wx.hideLoading()
      wx.showToast({ title: '资料已保存', icon: 'success' })
      setTimeout(() => {
        wx.navigateBack({ fail: () => wx.redirectTo({ url: '/package-client/pages/client-profile/index' }) })
      }, 500)
    } catch (error) {
      wx.hideLoading()
      console.error('[编辑资料] 保存失败', error)
      if (uploaded && api.upload && api.upload.delete) {
        try { await api.upload.delete(uploaded) } catch (cleanupError) {
          console.warn('[编辑资料] 回收未使用头像失败', cleanupError)
        }
      }
      if (error && error.message === '上传响应缺少头像地址') {
        wx.showToast({ title: error.message, icon: 'none' })
      }
    } finally {
      this.setData({ saving: false })
    }
  },

  onUnsupported() {
    wx.showToast({ title: '该资料字段尚未接入后端', icon: 'none' })
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.redirectTo({ url: '/package-client/pages/client-profile/index' }) })
  }
}))

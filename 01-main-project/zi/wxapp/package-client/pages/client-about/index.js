const app = getApp()

Page({
  data: { loading: true, loadError: '', title: '关于我们', content: '', updatedAt: '', versionText: '开发版' },

  onLoad() {
    try {
      const info = wx.getAccountInfoSync()
      const version = info && info.miniProgram && info.miniProgram.version
      const env = info && info.miniProgram && info.miniProgram.envVersion
      this.setData({ versionText: version || ({ develop: '开发版', trial: '体验版', release: '正式版' }[env] || '版本未标记') })
    } catch (error) {
      console.warn('读取小程序版本失败', error)
    }
    this.loadContent()
  },

  async loadContent() {
    this.setData({ loading: true, loadError: '' })
    try {
      const page = await app.getApi().pages.about()
      const content = page && typeof page.content === 'string' ? page.content.trim() : ''
      if (!content) throw new Error('平台介绍尚未配置')
      this.setData({
        title: page.title || '关于我们',
        content,
        updatedAt: page.updated_at || '',
        loading: false
      })
    } catch (error) {
      console.error('加载关于页面失败', error)
      this.setData({ loading: false, loadError: (error && error.message) || '内容加载失败' })
    }
  },

  onBack() { wx.navigateBack({ delta: 1 }) },
  onAgreement(e) {
    wx.navigateTo({ url: '/package-client/pages/client-agreement/index?document=' + encodeURIComponent(e.currentTarget.dataset.document) })
  },
  onFeedback() { wx.navigateTo({ url: '/package-client/pages/client-feedback/index' }) },
  onRetry() { this.loadContent() }
})

App({
  globalData: {
    baseURL: 'http://localhost:8000',
    token: null,
    userInfo: null
  },
  onLaunch() {
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
    }
  }
})

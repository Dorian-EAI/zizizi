// app.js — 自家人居家维修 玻璃新拟态版
const { mockApi } = require('./mock/api')
const realApi = require('./api/index.js')
const { getRuntimeConfig, DEV_STORAGE_KEYS } = require('./config/env')

const runtimeConfig = getRuntimeConfig()

App({
  globalData: {
    role: '',                // client | worker
    userInfo: null,
    token: '',
    envVersion: runtimeConfig.envVersion,
    baseURL: runtimeConfig.baseURL,
    servicePhone: runtimeConfig.servicePhone,
    allowMock: runtimeConfig.allowMock,
    useMock: runtimeConfig.useMock,
    // 保留兼容字段，但请求层不会再进行自动降级。
    useAutoFallback: false,
    systemInfo: null,
    statusBarHeight: 20,
    api: null,
    _authRedirecting: false
  },

  onLaunch() {
    // 读取本地角色与登录态
    try {
      const role = wx.getStorageSync('role')
      if (role) this.globalData.role = role
      const token = wx.getStorageSync('token')
      if (token) this.globalData.token = token
      const userInfo = wx.getStorageSync('userInfo')
      if (userInfo) this.globalData.userInfo = userInfo
    } catch (e) {}

    // 获取系统信息（状态栏高度、窗口尺寸）— 用 getWindowInfo 替代已弃用的 getSystemInfoSync
    let sys = null
    try {
      if (wx.getWindowInfo) {
        sys = wx.getWindowInfo()
      }
    } catch (e) { sys = null }
    // 极端兜底：取全局 systemInfo 同步版本（HarmonyOS 兼容）
    if (!sys) {
      try {
        const deprecated = wx.getSystemInfoSync && wx.getSystemInfoSync()
        sys = deprecated || {}
      } catch (e) { sys = {} }
    }
    this.globalData.systemInfo = sys
    this.globalData.statusBarHeight = sys.statusBarHeight || 20

    // 读取设备信息（HarmonyOS 平台判断，官方推荐从 wx.getDeviceInfo 获取）
    try {
      let deviceInfo = null
      if (wx.getDeviceInfo) {
        deviceInfo = wx.getDeviceInfo()
      } else if (wx.getSystemInfoSync) {
        deviceInfo = wx.getSystemInfoSync()
      }
      if (deviceInfo) {
        this.globalData.platform = deviceInfo.platform || deviceInfo.system || ''
        this.globalData.deviceModel = deviceInfo.model || ''
      }
    } catch (e) {}

    // 基础库版本提示（3.17.0 为灰度版，用户若遇怪问题可在控制台看见）
    // SDKVersion 推荐从 wx.getAppBaseInfo() 取，避免 getSystemInfoSync 弃用告警
    try {
      let SDKVersion = ''
      if (wx.getAppBaseInfo) {
        const appBaseInfo = wx.getAppBaseInfo()
        SDKVersion = (appBaseInfo && appBaseInfo.SDKVersion) || ''
      } else if (wx.getSystemInfoSync) {
        const old = wx.getSystemInfoSync()
        SDKVersion = (old && old.SDKVersion) || ''
      }
      if (SDKVersion && SDKVersion.indexOf('3.17') === 0) {
        console.warn(
          '[启动提示] 当前基础库 SDKVersion=' + SDKVersion +
          ' 为灰度版本。若出现样式/数据渲染异常，' +
          '请在开发者工具"详情→本地设置→调试基础库"切换为稳定版（如 3.0.0 / 2.33.0）'
        )
      }
    } catch (e) {}

    // 加载 zjrnew 本地化衬线字体（失败时自动走 WXSS fallback，不阻塞启动）
    this.loadLocalFonts()

    // Mock 只能由开发者在 develop 环境显式启用，体验版/正式版始终使用真实 API。
    this.globalData.api = this.globalData.useMock ? mockApi : realApi

    if (this.globalData.useMock) {
      console.info('[运行环境] develop 显式 Mock 模式')
    } else if (!this.globalData.baseURL) {
      console.error('[运行环境] ' + this.globalData.envVersion + ' 未配置 API baseURL')
    }

    // 仅在已有登录态时验证 Token；未登录用户留在入口页完成微信登录。
    if (this.globalData.token) this.probeBackend()
  },

  // 本地字体加载：微信运行时不稳定支持包内字体 URL；保留系统衬线降级，避免无效 URL 告警
  loadLocalFonts() {
    if (!wx.loadFontFace) return
    // 展示数字/标题统一通过系统衬线字体栈降级。
    // 若后续接入 HTTPS CDN 字体地址，可在这里恢复 wx.loadFontFace。
  },

  // 启动探测仅验证已有 Token。网络异常保留登录态，401 才清理并回到入口页。
  probeBackend() {
    return new Promise((resolve) => {
      if (this.globalData.useMock) { resolve(true); return }
      if (!this.globalData.token || !this.globalData.baseURL) { resolve(false); return }
      try {
        const url = this.globalData.baseURL + '/api/auth/me'
        wx.request({
          url,
          method: 'GET',
          timeout: 5000,
          header: {
            'Authorization': this.globalData.token ? ('Bearer ' + this.globalData.token) : ''
          },
          success: (res) => {
            if (res.statusCode >= 200 && res.statusCode < 300) {
              resolve(true)
            } else if (res.statusCode === 401) {
              this.handleUnauthorized()
              resolve(false)
            } else {
              console.warn('[启动探测] 后端响应 HTTP ' + res.statusCode)
              resolve(false)
            }
          },
          fail: (error) => {
            console.warn('[启动探测] 网络不可用，未切换 Mock', error)
            resolve(false)
          }
        })
      } catch (e) {
        console.warn('[启动探测] 请求初始化失败', e)
        resolve(false)
      }
    })
  },

  // 兼容旧调用：生产链路禁止失败后自动切换到 Mock。
  _applyFallback() {
    console.warn('[运行环境] 已禁止自动降级 Mock；请修复真实接口或在 develop 显式启用 Mock')
    return false
  },

  handleUnauthorized(options) {
    if (this.globalData.useMock) return
    this.clearLogin()

    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
    const top = pages[pages.length - 1]
    if (top && top.route === 'pages/entry/index') return
    if (this.globalData._authRedirecting) return
    this.globalData._authRedirecting = true

    if (!options || !options.silent) {
      wx.showToast({ title: '登录已过期，请重新登录', icon: 'none', duration: 1600 })
    }
    wx.reLaunch({
      url: '/pages/entry/index?reason=expired',
      fail: () => { this.globalData._authRedirecting = false }
    })
  },

  // 切换角色并持久化
  setRole(role) {
    this.globalData.role = role
    try { wx.setStorageSync('role', role) } catch (e) {}
  },

  // 获取 API（真实或 mock，统一入口）
  getApi() {
    if (!this.globalData.api) {
      this.globalData.api = this.globalData.useMock ? mockApi : realApi
    }
    return this.globalData.api
  },

  // 切换 mock / 真实后端模式
  setUseMock(useMock) {
    const enabled = useMock === true
    if (enabled && !this.globalData.allowMock) {
      console.error('[运行环境] 体验版/正式版禁止启用 Mock')
      return false
    }
    this.globalData.useMock = enabled
    this.globalData.api = enabled ? mockApi : realApi
    if (this.globalData.envVersion === 'develop') {
      try { wx.setStorageSync(DEV_STORAGE_KEYS.USE_MOCK, enabled) } catch (e) {}
    }
    return true
  },

  // 保存登录态
  saveLogin(token, userInfo, role) {
    this.globalData.token = token
    this.globalData.userInfo = userInfo
    this.globalData._authRedirecting = false
    if (role) {
      this.globalData.role = role
      try { wx.setStorageSync('role', role) } catch (e) {}
    }
    try {
      wx.setStorageSync('token', token)
      if (userInfo) wx.setStorageSync('userInfo', userInfo)
      else wx.removeStorageSync('userInfo')
    } catch (e) {}
  },

  // 清除登录态
  clearLogin() {
    this.globalData.token = ''
    this.globalData.userInfo = null
    try {
      wx.removeStorageSync('token')
      wx.removeStorageSync('userInfo')
    } catch (e) {}
  }
})

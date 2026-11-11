// 小程序运行环境配置。
// 体验版与正式版必须填写真实 HTTPS API 地址；留空时请求层会明确报错，绝不降级到 Mock。
const ENVIRONMENTS = {
  develop: {
    baseURL: 'http://localhost:8000',
    servicePhone: '',
    allowMock: true,
    useMock: true,
    // 自有对象存储 CDN 根地址（如 https://cdn.example.com/fonts，结尾不要带 /）。
    // 留空 → 使用主包内嵌 base64 衬线字体（约 600KB，最稳但占主包体积）。
    // 配置后 → font.js 改走网络加载，主包可删除 assets/fonts/fonts.js 瘦身到约 1.1MB。
    fontCDN: ''
  },
  trial: {
    baseURL: '',          // 提审/体验前必填：体验版 HTTPS API 地址
    servicePhone: '',      // 提审/体验前必填：客服电话（用于《服务条款》展示与申诉入口）
    allowMock: false,
    useMock: false,
    fontCDN: ''           // 可选：自有字体 CDN 根地址；留空则用主包内嵌
  },
  release: {
    baseURL: '',          // 正式上线前必填：生产 HTTPS API 地址
    servicePhone: '',      // 正式上线前必填：客服电话
    allowMock: false,
    useMock: false,
    fontCDN: ''           // 可选：自有字体 CDN 根地址；留空则用主包内嵌
  },
  // 微信未返回合法 envVersion 时 fail closed，禁止读取任何开发机覆盖项。
  invalid: {
    baseURL: '',
    servicePhone: '',
    allowMock: false,
    useMock: false,
    fontCDN: ''
  }
}

const DEV_STORAGE_KEYS = {
  BASE_URL: '__DEV_API_BASE_URL__',
  USE_MOCK: '__DEV_USE_MOCK__'
}

function getEnvVersion() {
  try {
    const info = wx.getAccountInfoSync && wx.getAccountInfoSync()
    const version = info && info.miniProgram && info.miniProgram.envVersion
    if (version === 'develop' || version === 'trial' || version === 'release') return version
  } catch (e) {}
  return 'invalid'
}

function readDevSetting(key) {
  try {
    return wx.getStorageSync(key)
  } catch (e) {
    return undefined
  }
}

function trimBaseURL(value) {
  return String(value || '').trim().replace(/\/+$/, '')
}

function getRuntimeConfig() {
  const envVersion = getEnvVersion()
  const preset = ENVIRONMENTS[envVersion]
  let baseURL = preset.baseURL
  let useMock = false

  // 只有开发版允许通过开发者工具显式覆盖；体验版/正式版不读取本地开关。
  if (envVersion === 'develop') {
    const localBaseURL = readDevSetting(DEV_STORAGE_KEYS.BASE_URL)
    const localUseMock = readDevSetting(DEV_STORAGE_KEYS.USE_MOCK)
    if (localBaseURL) baseURL = localBaseURL
    useMock = preset.useMock === true || localUseMock === true || localUseMock === 'true'
  }

  return {
    envVersion,
    baseURL: trimBaseURL(baseURL),
    servicePhone: String(preset.servicePhone || '').trim(),
    fontCDN: trimBaseURL(preset.fontCDN),
    allowMock: preset.allowMock === true,
    useMock: preset.allowMock === true && useMock
  }
}

module.exports = {
  ENVIRONMENTS,
  DEV_STORAGE_KEYS,
  getEnvVersion,
  getRuntimeConfig,
  trimBaseURL
}

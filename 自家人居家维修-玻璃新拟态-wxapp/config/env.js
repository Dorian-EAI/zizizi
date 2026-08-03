// 小程序运行环境配置。
// 体验版与正式版必须填写真实 HTTPS API 地址；留空时请求层会明确报错，绝不降级到 Mock。
const ENVIRONMENTS = {
  develop: {
    baseURL: 'http://localhost:8000',
    servicePhone: '',
    allowMock: true,
    useMock: false
  },
  trial: {
    baseURL: '',
    servicePhone: '',
    allowMock: false,
    useMock: false
  },
  release: {
    baseURL: '',
    servicePhone: '',
    allowMock: false,
    useMock: false
  },
  // 微信未返回合法 envVersion 时 fail closed，禁止读取任何开发机覆盖项。
  invalid: {
    baseURL: '',
    servicePhone: '',
    allowMock: false,
    useMock: false
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

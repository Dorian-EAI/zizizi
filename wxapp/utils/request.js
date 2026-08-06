// HTTP 请求封装：统一业务响应、鉴权失效处理与请求去重。
// 真实接口失败会如实失败；任何环境都不会在网络错误或 401 后自动切换 Mock。
const storage = require('./storage')

const IN_FLIGHT = new Map()
const AUTH_ERROR_CODE = 'AUTH_REQUIRED'
const CONFIG_ERROR_CODE = 'API_BASE_URL_MISSING'

function stableKey(obj) {
  if (obj === null || obj === undefined) return ''
  return typeof obj === 'string' ? obj : JSON.stringify(obj)
}

function createError(message, code, statusCode, cause) {
  const error = new Error(message)
  if (code) error.code = code
  if (statusCode) error.statusCode = statusCode
  if (cause) error.cause = cause
  return error
}

function getErrorMessage(data, fallback) {
  if (!data) return fallback
  const detail = data.detail
  if (Array.isArray(detail)) {
    const messages = detail.map(item => item && item.msg).filter(Boolean)
    if (messages.length) return messages.join('；')
  }
  if (typeof detail === 'string') return detail
  return data.msg || data.message || fallback
}

function buildHeader(extra, jsonContentType) {
  const token = storage.get(storage.KEYS.TOKEN)
  const headers = {}
  if (jsonContentType !== false) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = 'Bearer ' + token
  return Object.assign(headers, extra || {})
}

function showError(message, silent) {
  if (!silent && message) wx.showToast({ title: message, icon: 'none' })
}

function handleUnauthorized(silent) {
  storage.remove(storage.KEYS.TOKEN)
  storage.remove(storage.KEYS.USER)
  const app = getApp()
  if (app && typeof app.handleUnauthorized === 'function') {
    app.handleUnauthorized({ silent: !!silent })
  } else if (!silent) {
    wx.reLaunch({ url: '/pages/entry/index?reason=expired' })
  }
  return createError('登录已过期，请重新登录', AUTH_ERROR_CODE, 401)
}

function resolveRequestURL(app, path) {
  if (/^https?:\/\//i.test(path)) return path
  const globalData = app && app.globalData ? app.globalData : {}
  const baseURL = String(globalData.baseURL || '').replace(/\/+$/, '')
  const envVersion = globalData.envVersion || 'invalid'

  if (!baseURL) {
    throw createError(
      envVersion + ' 环境未配置 API 地址',
      CONFIG_ERROR_CODE
    )
  }
  if (!/^https?:\/\//i.test(baseURL)) {
    throw createError('API 地址必须以 http:// 或 https:// 开头', CONFIG_ERROR_CODE)
  }
  if (envVersion !== 'develop' && !/^https:\/\//i.test(baseURL)) {
    throw createError('体验版和正式版必须使用 HTTPS API 地址', CONFIG_ERROR_CODE)
  }
  return baseURL + (path.charAt(0) === '/' ? path : '/' + path)
}

function cleanParams(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return data
  const cleaned = {}
  Object.keys(data).forEach(key => {
    const value = data[key]
    if (value !== null && value !== undefined && value !== '') cleaned[key] = value
  })
  return cleaned
}

function unwrapSuccessResponse(res) {
  const data = res.data
  if (data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'code')) {
    if (data.code !== 0 && data.code !== 200) {
      throw createError(getErrorMessage(data, '请求失败'), 'BUSINESS_ERROR', res.statusCode)
    }
    return data.data !== undefined ? data.data : data
  }
  return data
}

function handleResponse(res, silent) {
  if (res.statusCode === 401) throw handleUnauthorized(silent)
  if (res.statusCode === 429) {
    throw createError('操作太频繁，请稍后再试', 'RATE_LIMITED', 429)
  }
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw createError(
      getErrorMessage(res.data, '请求失败（HTTP ' + res.statusCode + '）'),
      'HTTP_ERROR',
      res.statusCode
    )
  }
  return unwrapSuccessResponse(res)
}

function request(options) {
  const app = getApp()
  const config = options || {}
  const url = config.url
  const method = String(config.method || 'GET').toUpperCase()
  const silent = config.silent === true
  const finalData = method === 'GET' ? cleanParams(config.data) : config.data
  const finalHeader = buildHeader(config.header)
  let requestURL

  try {
    requestURL = resolveRequestURL(app, url)
  } catch (error) {
    showError(error.message, silent)
    return Promise.reject(error)
  }

  // 幂等键等自定义请求头也是命令身份的一部分，不能把
  // 两个不同金融命令错误合并为同一个 in-flight Promise。
  const key = method + '::' + requestURL + '::' + stableKey(finalData) + '::' + stableKey(finalHeader)
  if (IN_FLIGHT.has(key)) return IN_FLIGHT.get(key)

  const promise = new Promise((resolve, reject) => {
    wx.request({
      url: requestURL,
      method,
      data: finalData,
      header: finalHeader,
      timeout: config.timeout || 15000,
      success(res) {
        try {
          resolve(handleResponse(res, silent))
        } catch (error) {
          showError(error.message, silent || error.code === AUTH_ERROR_CODE)
          reject(error)
        }
      },
      fail(error) {
        const requestError = createError('网络异常，请稍后重试', 'NETWORK_ERROR', 0, error)
        requestError.errMsg = error && error.errMsg
        showError(requestError.message, silent)
        reject(requestError)
      }
    })
  })

  const clean = () => IN_FLIGHT.delete(key)
  promise.then(clean, clean)
  IN_FLIGHT.set(key, promise)
  return promise
}

function uploadFile(options) {
  const app = getApp()
  const config = options || {}
  const silent = config.silent === true
  let requestURL

  try {
    requestURL = resolveRequestURL(app, config.url)
  } catch (error) {
    showError(error.message, silent)
    return Promise.reject(error)
  }

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: requestURL,
      filePath: config.filePath,
      name: config.name || 'file',
      formData: config.formData,
      header: buildHeader(config.header, false),
      timeout: config.timeout || 30000,
      success(res) {
        let payload
        try {
          payload = typeof res.data === 'string' ? JSON.parse(res.data) : res.data
        } catch (error) {
          const parseError = createError('上传响应解析失败', 'UPLOAD_RESPONSE_INVALID', res.statusCode, error)
          showError(parseError.message, silent)
          reject(parseError)
          return
        }

        try {
          resolve(handleResponse({ statusCode: res.statusCode, data: payload }, silent))
        } catch (error) {
          showError(error.message || '上传失败', silent || error.code === AUTH_ERROR_CODE)
          reject(error)
        }
      },
      fail(error) {
        const uploadError = createError('网络异常，上传失败', 'NETWORK_ERROR', 0, error)
        uploadError.errMsg = error && error.errMsg
        showError(uploadError.message, silent)
        reject(uploadError)
      }
    })
  })
}

module.exports = {
  get: (url, data, opts) => request(Object.assign({ url, method: 'GET', data }, opts || {})),
  post: (url, data, opts) => request(Object.assign({ url, method: 'POST', data }, opts || {})),
  put: (url, data, opts) => request(Object.assign({ url, method: 'PUT', data }, opts || {})),
  del: (url, data, opts) => request(Object.assign({ url, method: 'DELETE', data }, opts || {})),
  request,
  uploadFile,
  AUTH_ERROR_CODE,
  CONFIG_ERROR_CODE
}

// 由设计页生成器创建的最小运行控制器。
// 默认只允许画布登记的本地导航；未接入真实契约的动作明确受限，不伪造成功。
function safeRoute(value) {
  const route = String(value || '')
  return /^\/pages\/[a-z0-9-]+\/index(?:\?[A-Za-z0-9_.~!$&'()*+,;=:@%/?-]*)?$/.test(route)
    ? route
    : ''
}

function appendQuery(route, key, value) {
  if (!value) return route
  return route + (route.indexOf('?') >= 0 ? '&' : '?') + key + '=' + encodeURIComponent(String(value))
}

const SUPPORTED_FALLBACKS = {
  'page-worker-appeal-detail': ['/package-worker/pages/worker-appeal/index', '前往申诉中心'],
  'page-worker-cert-manage': ['/package-worker/pages/worker-certification/index', '前往师傅认证'],
  'page-worker-certificate-edit': ['/package-worker/pages/worker-certification/index', '前往师傅认证'],
  'page-worker-chat': ['/pages/worker-orders/index', '返回订单中心'],
  'page-worker-customer-profile': ['/pages/worker-orders/index', '返回订单中心'],
  'page-worker-deposit-pay': ['/package-worker/pages/worker-deposit/index', '前往保证金中心'],
  'page-worker-deposit-refund': ['/package-worker/pages/worker-deposit/index', '前往保证金中心'],
  'page-worker-exam-result': ['/package-worker/pages/worker-training/index', '前往培训中心'],
  'page-worker-experience': ['/pages/worker-profile/index', '返回个人中心'],
  'page-worker-experience-item-edit': ['/pages/worker-profile/index', '返回个人中心'],
  'page-worker-help': ['/package-worker/pages/worker-appeal/index', '联系平台客服'],
  'page-worker-help-category': ['/package-worker/pages/worker-appeal/index', '联系平台客服'],
  'page-worker-income-category-detail': ['/package-worker/pages/worker-transactions/index', '查看真实资金流水'],
  'page-worker-income-stat': ['/package-worker/pages/worker-transactions/index', '查看真实资金流水'],
  'page-worker-lesson': ['/package-worker/pages/worker-training/index', '前往培训中心'],
  'page-worker-order-setting': ['/package-worker/pages/worker-settings/index', '返回设置'],
  'page-worker-price-adjust-worker': ['/pages/worker-orders/index', '返回订单中心'],
  'page-worker-service-area': ['/package-worker/pages/worker-settings/index', '返回设置'],
  'page-worker-service-scope': ['/package-worker/pages/worker-settings/index', '返回设置'],
  'page-worker-time-setting': ['/package-worker/pages/worker-settings/index', '返回设置'],
  'page-worker-training-detail': ['/package-worker/pages/worker-training/index', '前往培训中心'],
  'page-worker-withdraw-result': ['/package-worker/pages/worker-transactions/index', '查看真实资金流水']
}

function createDesignPage(config) {
  const options = config || {}
  const fallback = SUPPORTED_FALLBACKS[options.pageId] || []
  return {
    data: {
      pageId: options.pageId || '',
      pageTitle: options.title || '功能说明',
      sourceHash: options.sourceHash || '',
      businessAvailable: false,
      restrictedTitle: (options.title || '当前功能') + '尚未接入真实数据',
      restrictedMessage: '此页面没有可验证的业务接口，画布示例数据已隐藏，本次不会读取或修改真实业务数据。',
      fallbackRoute: fallback[0] || '',
      fallbackLabel: fallback[1] || ''
    },

    onLoad(query) {
      this._designQuery = query || {}
    },

    onNavigate(event) {
      const dataset = event && event.currentTarget && event.currentTarget.dataset || {}
      let route = safeRoute(dataset.route)
      if (!route) {
        wx.showToast({ title: '页面入口未配置', icon: 'none' })
        return
      }
      if (dataset.document) route = appendQuery(route, 'document', dataset.document)
      wx.navigateTo({
        url: route,
        fail: error => {
          console.warn('[设计页导航失败]', options.route, route, error)
          wx.showToast({ title: '目标页面暂不可用', icon: 'none' })
        }
      })
    },

    onBack() {
      wx.navigateBack({
        delta: 1,
        fail: () => {
          if (this.data.fallbackRoute) this.onOpenSupported()
        }
      })
    },

    onAction(event) {
      const dataset = event && event.currentTarget && event.currentTarget.dataset || {}
      const action = String(dataset.action || '')
      const handlerName = action ? 'action_' + action.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()) : ''
      if (handlerName && typeof this[handlerName] === 'function') {
        return this[handlerName](event)
      }
      wx.showToast({ title: this.data.restrictedMessage, icon: 'none' })
    },

    onOpenSupported() {
      let route = safeRoute(this.data.fallbackRoute)
      if (!route) return
      const query = this._designQuery || {}
      ;['orderId', 'courseId', 'ticketId'].forEach(key => {
        if (query[key]) route = appendQuery(route, key, query[key])
      })
      wx.navigateTo({
        url: route,
        fail: error => {
          console.warn('[已接入入口导航失败]', options.route, route, error)
          wx.showToast({ title: '目标页面暂不可用', icon: 'none' })
        }
      })
    }
  }
}

module.exports = { createDesignPage }

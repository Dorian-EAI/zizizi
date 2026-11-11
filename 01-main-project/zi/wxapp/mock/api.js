// mock/api.js — 模拟 API 实现
// 返回 Promise，模拟网络延迟
// 同时支持旧版扁平 API（如 getClientOrders）与新版命名空间 API（如 api.orders.list）
const data = require('./data')

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms || 200))
}

// ===== 命名空间 mock 实现（与 api/index.js 结构对齐）=====
const noop = async () => {
  await delay(100)
  return null
}
const empty = async () => {
  await delay(100)
  return []
}

const mockNotificationSettings = {
  push_order: true,
  push_system: true,
  push_activity: false,
  push_sms: false
}

const namespacedMock = {
  // 认证 / 用户
  auth: {
    wxLogin: async (code, userInfo) => {
      await delay(300)
      return { token: 'mock-token-' + Date.now(), user: data.userInfo }
    },
    workerLogin: async (phone, smsCode) => {
      await delay(300)
      return { token: 'mock-token-' + Date.now(), user: data.workerInfo }
    },
    me: async () => {
      await delay()
      return data.userInfo
    },
    workerMe: async () => {
      await delay()
      return data.workerInfo
    },
    submitCertification: async (application) => {
      await delay(300)
      return {
        certified: 1,
        certification_status: 'pending',
        application: Object.assign({}, application, { id_card: undefined })
      }
    },
    updateProfile: async (d) => {
      await delay(150)
      if (d && d.nickname !== undefined) data.userInfo.name = d.nickname
      Object.assign(data.userInfo, d || {})
      return Object.assign({}, data.userInfo)
    },
    bindPhone: async (phone, verificationCode) => {
      await delay(150)
      if (verificationCode !== '123456') throw new Error('验证码错误或已过期')
      data.userInfo.phone = phone
      return Object.assign({}, data.userInfo)
    },
    switchRole: noop,
    logout: noop,
    getAddresses: async () => {
      await delay()
      return data.addresses
    },
    addAddress: async (addr) => Object.assign({ id: 'a' + Date.now() }, addr),
    updateAddress: async (id, addr) => Object.assign({ id }, addr),
    deleteAddress: noop,
    setDefaultAddress: noop
  },

  // 服务
  services: {
    list: async () => {
      await delay()
      return data.services
    },
    detail: async (key) => {
      await delay()
      return data.services.find(s => s.key === key) || data.services[0]
    },
    categories: async () => {
      await delay()
      return data.categories
    },
    search: async (keyword) => {
      await delay(300)
      return data.services.filter(s => s.name.indexOf(keyword) >= 0 || s.desc.indexOf(keyword) >= 0)
    },
    hotTags: async () => {
      await delay(100)
      return data.hotTags
    },
    platformStats: async () => {
      await delay()
      return data.platformStats
    },
    workers: async () => {
      await delay()
      return data.workers
    },
    workerDetail: async (id) => {
      await delay()
      return data.workers.find(w => w.id === id) || data.workers[0]
    }
  },

  // 订单
  orders: {
    create: async (d) => Object.assign({ success: true, id: 'o' + Date.now() }, d),
    list: async (status) => {
      await delay()
      if (!status || status === 'all') return data.clientOrders
      return data.clientOrders.filter(o => o.status === status)
    },
    available: empty,
    workerList: async (status) => {
      await delay()
      if (!status || status === 'all') return data.workerOrders
      return data.workerOrders.filter(o => o.status === status)
    },
    detail: async (id) => {
      await delay()
      return data.clientOrders.find(o => o.id === id) || data.clientOrders[0]
    },
    workerDetail: async (id) => {
      await delay()
      return data.workerOrders.find(o => o.id === id) || data.workerOrders[0]
    },
    bidding: async (orderId, d) => ({ success: true, orderId, ...d }),
    listBiddings: async (orderId) => {
      await delay(300)
      return data.quotes
    },
    selectBidding: async (orderId, biddingId) => ({ success: true, orderId, biddingId }),
    updateStatus: async (id, status, extra) => ({ success: true, id, status, ...extra }),
    cancel: async (id) => ({ success: true, id }),
    review: async (id, d) => ({ success: true, id, ...d })
  },

  // 评价
  reviews: {
    list: empty,
    stats: async () => ({ total: 0, avgRating: 5 }),
    reply: noop,
    like: noop,
    mine: empty,
    workerDetail: async (workerId, params) => ({ workerId, list: [], avgRating: 4.9 })
  },

  // 收藏
  favorite: {
    toggleWorker: async (workerId) => ({ success: true, workerId, favorited: true }),
    listWorkers: async () => {
      await delay()
      return data.workers.slice(0, 2)
    },
    existsWorker: async (workerId) => ({ exists: true, workerId }),
    getWorker: async (workerId) => data.workers.find(w => w.id === workerId)
  },

  // 钱包
  wallet: {
    detail: async () => {
      await delay()
      return data.workerWallet
    },
    transactions: empty,
    recharge: async (amount) => ({ success: true, amount }),
    withdraw: async (amount) => {
      await delay(800)
      return { success: true, amount, time: new Date().toLocaleString() }
    },
    pay: noop,
    refund: noop,
    offlineConfirm: noop
  },

  // 微信支付
  wxpay: {
    rechargeJsapi: async (amount) => ({ timeStamp: '', nonceStr: '', package: '', signType: 'MD5', paySign: '' }),
    paymentStatus: async () => ({ status: 'pending' }),
    orderJsapi: async (orderId, paymentMethod) => ({ timeStamp: '', nonceStr: '', package: '', signType: 'MD5', paySign: '' })
  },

  // 优惠券
  coupon: {
    templates: empty,
    claim: async (templateId) => ({ success: true, templateId }),
    mine: async (status) => {
      await delay()
      if (!status) return data.coupons
      return data.coupons.filter(c => c.status === status)
    },
    available: empty
  },

  // 上传
  upload: {
    image: async (filePath) => ({ url: 'https://placehold.co/200x200?text=mock' }),
    images: async (filePath) => ({ urls: ['https://placehold.co/200x200?text=mock'] }),
    delete: noop,
    ossPolicy: async () => ({})
  },

  // 消息
  messages: {
    list: empty,
    unreadCount: async () => 0,
    markRead: noop,
    markAllRead: noop,
    remove: noop
  },

  // AI
  ai: {
    analyze: async (d) => ({ suggestion: 'mock 建议' }),
    chat: async (d) => ({ reply: '这是 AI 助手的模拟回复' }),
    estimate: async (d) => ({ priceRange: '¥100-300' }),
    quickQuestions: async () => (['漏水怎么办？', '电路跳闸？', '空调不制冷？']),
    agentTurn: async () => ({
      session_id: 'mock_session',
      status: 'collecting',
      reply: '当前是 Mock 模式，请切换到真实接口后再体验 AI 下单。',
      actions: [],
      missing: [],
      options: {},
      draft: null,
      order: null
    }),
    agentSession: async () => ({
      session_id: 'mock_session',
      status: 'collecting',
      reply: '',
      actions: [],
      missing: [],
      options: {},
      draft: null,
      order: null
    })
  },

  // 会员
  member: {
    detail: async () => ({ level: '普通会员', growth: 0, benefits: [] }),
    benefits: empty,
    addGrowth: async (amount) => ({ success: true, amount })
  },

  // 积分
  points: {
    detail: async () => ({ balance: 0 }),
    logs: empty,
    signin: async () => ({ success: true, gained: 10 }),
    exchangeCoupon: async (ruleId) => ({ success: true, ruleId })
  },

  // 反馈
  feedback: {
    create: async (d) => ({ success: true, id: 'f' + Date.now(), ...d }),
    mine: empty,
    update: async (id, d) => ({ success: true, id, ...d })
  },

  // 内容页
  pages: {
    faqs: empty,
    agreement: async () => ({ content: 'mock 协议' }),
    privacy: async () => ({ content: 'mock 隐私政策' }),
    about: async () => ({ content: 'mock 关于我们' }),
    help: async () => ({ content: 'mock 帮助' }),
    byKey: async (key) => ({ content: 'mock ' + key })
  },

  // 通知设置
  settings: {
    getNotification: async () => Object.assign({}, mockNotificationSettings),
    updateNotification: async (d) => {
      Object.assign(mockNotificationSettings, d || {})
      return Object.assign({}, mockNotificationSettings)
    }
  },

  // 实时位置追踪（PRD v6.0 核心）
  track: {
    report: async (orderId, d) => ({
      success: true,
      orderId,
      latitude: d.latitude || d.lat,
      longitude: d.longitude || d.lng,
      heading: d.heading || 0,
      speed: d.speed || 0,
      last_reported_at: new Date().toISOString()
    }),
    depart: async (orderId) => ({ success: true, orderId, status: 'departing' }),
    arrive: async (orderId) => ({ success: true, orderId, status: 'arrived' }),
    startService: async (orderId) => ({ success: true, orderId, status: 'serving' }),
    checkin: async (orderId, d) => ({ success: true, orderId, ...d }),
    checkinAbnormal: async (orderId, d) => ({ success: true, orderId, ...d }),
    tracking: async (orderId) => {
      const order = data.clientOrders.find(o => o.id === orderId) || data.clientOrders[1]
      const now = new Date()
      return {
        orderId,
        status: order.status === 'accepted' ? 'departing' : (order.status || 'departing'),
        worker: {
          id: order.workerId || 'w1',
          name: order.workerName || '张师傅',
          phone: order.workerPhone || '139****6666',
          rating: 4.8,
          vehicle: '专业维修师傅',
          lat: 39.9042,
          lng: 116.4074,
          heading: 35,
          speed: 5.8
        },
        destination: {
          name: '客户家',
          address: order.address || '朝阳区建国路88号',
          lat: order.lat || 39.9050,
          lng: order.lng || 116.4080
        },
        eta: { minutes: 10, distance: '1.5km' },
        eta_seconds: 600,
        distance_meters: 1500,
        lastUpdate: now.toISOString(),
        route: [
          { latitude: 39.9042, longitude: 116.4074 },
          { latitude: 39.9045, longitude: 116.4077 },
          { latitude: 39.9048, longitude: 116.4079 },
          { latitude: 39.9050, longitude: 116.4080 }
        ],
        steps: {
          accepted: '09:00',
          departing: '09:05',
          arrived: '',
          serving: '',
          completed: ''
        }
      }
    },
    routeHistory: async (orderId) => [
      { latitude: 39.9042, longitude: 116.4074 },
      { latitude: 39.9045, longitude: 116.4077 },
      { latitude: 39.9048, longitude: 116.4079 },
      { latitude: 39.9050, longitude: 116.4080 }
    ],
    trackInfo: async (orderId) => ({ orderId, status: 'departing' })
  },

  // 额外费用
  extraFee: {
    create: async (orderId, d) => ({ success: true, orderId, ...d }),
    list: async (orderId) => [],
    approve: async (orderId, feeId) => ({ success: true, orderId, feeId }),
    reject: async (orderId, feeId, reason) => ({ success: true, orderId, feeId, reason })
  },

  // 保险
  insurance: {
    buy: async (orderId, d) => ({ success: true, orderId, ...d }),
    policy: async (orderId) => ({ orderId, policyNo: 'mock-001' }),
    claim: async (d) => ({ success: true, id: 'c' + Date.now(), ...d }),
    claims: empty
  },

  // 师傅保证金
  deposit: {
    pay: async (amount) => ({ success: true, amount }),
    detail: async () => ({ amount: 0, paid: 0 }),
    refund: async () => ({ success: true })
  },

  // 家庭年卡
  annualCard: {
    templates: empty,
    purchase: async (d) => ({ success: true, id: 'ac' + Date.now(), ...d }),
    mine: empty,
    use: async (d) => ({ success: true, ...d }),
    refund: async (cardId) => ({ success: true, cardId })
  },

  // 质检回访
  quality: {
    inspect: async (orderId, d) => ({ success: true, orderId, ...d }),
    feedback: async (inspectionId, d) => ({ success: true, inspectionId, ...d }),
    myInspections: empty
  },

  // 培训考试
  training: {
    courses: empty,
    start: async (courseId) => ({ success: true, courseId }),
    complete: async (courseId) => ({ success: true, courseId }),
    exam: async (courseId) => ({ courseId, questions: [] }),
    submitExam: async (courseId, answers) => ({ success: true, courseId, score: 90 }),
    records: empty,
    stats: async () => ({ total: 0, completed: 0 })
  },

  // 客服工单
  ticket: {
    create: async (d) => ({ success: true, id: 't' + Date.now(), ...d }),
    mine: empty,
    detail: async (ticketId) => ({ id: ticketId, status: 'pending' }),
    reply: async (ticketId, content) => ({ success: true, ticketId, content })
  },

  // 动态定价
  pricing: {
    currentSurcharge: async () => ({ surcharge: 0, reason: '正常时段' }),
    calculate: async (d) => ({ total: 100, ...d })
  },

  // 地图服务
  map: {
    distance: async (params) => ({ distance: 1.2, duration: 10 }),
    reverseGeocode: async (lat, lng) => ({ address: '模拟地址' }),
    geocode: async (address) => ({ lat: 39.9042, lng: 116.4074 }),
    config: async () => ({ provider: 'local' })
  },

  // 短信
  sms: {
    sendCode: async (phone, scene) => ({ sent: true, phone, scene, code: '123456' }),
    verifyCode: async (phone, code, scene) => ({ success: true, phone, scene })
  }
}

// ===== 旧版扁平 API（兼容现有页面直接调用）=====
const mockApi = Object.assign({}, {
  // 服务
  getServices:        () => namespacedMock.services.list(),
  getServiceDetail:  (key) => namespacedMock.services.detail(key),
  getCategories:      () => namespacedMock.services.categories(),
  getPlatformStats:    () => namespacedMock.services.platformStats(),
  // 师傅
  getWorkers:         () => namespacedMock.services.workers(),
  getWorkerDetail:    (id) => namespacedMock.services.workerDetail(id),
  // 客户端订单
  getClientOrders:    (status) => namespacedMock.orders.list(status),
  getOrderDetail:     (id) => namespacedMock.orders.detail(id),
  getQuotes:           (orderId) => namespacedMock.orders.listBiddings(orderId),
  publishOrder:        (data) => namespacedMock.orders.create(data),
  selectQuote:         (orderId, quoteId) => namespacedMock.orders.selectBidding(orderId, quoteId),
  cancelOrder:         (orderId) => namespacedMock.orders.cancel(orderId),
  // 师傅端订单
  getWorkerOrders:     (status) => namespacedMock.orders.workerList(status),
  getWorkerOrderDetail:(id) => namespacedMock.orders.workerDetail(id),
  acceptOrder:         (id, price) => namespacedMock.orders.bidding(id, { price }),
  submitQuote:         (orderId, price, eta) => namespacedMock.orders.bidding(orderId, { price, eta }),
  updateOrderStep:     (orderId, step, extra) => namespacedMock.orders.updateStatus(orderId, step, extra),
  // 地址
  getAddresses:        () => namespacedMock.auth.getAddresses(),
  addAddress:          (addr) => namespacedMock.auth.addAddress(addr),
  // 钱包
  getWorkerWallet:     () => namespacedMock.wallet.detail(),
  withdraw:            (amount) => namespacedMock.wallet.withdraw(amount),
  getTransactions:     (params) => namespacedMock.wallet.transactions(params),
  // 用户
  getUserInfo:         () => namespacedMock.auth.me(),
  getWorkerInfo:       () => namespacedMock.auth.workerMe(),
  // 优惠券
  getCoupons:          (status) => namespacedMock.coupon.mine(status),
  // 搜索
  search:              (keyword) => namespacedMock.services.search(keyword),
  getHotTags:          () => namespacedMock.services.hotTags()
}, namespacedMock) // 命名空间附加到根上

module.exports = { mockApi }

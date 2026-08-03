// api/index.js — 真实后端 API 封装（对接后端使用）
// 后端基地址: http://localhost:8000 (不含 /api 前缀, 所有路径完整写 /api/xxx)
// 后端响应: { code, msg, data }
const http = require('../utils/request')

module.exports = {
  // ==================== 认证 / 用户 ====================
  auth: {
    wxLogin:    (code, userInfo) => http.post('/api/auth/wx-login', {
      code,
      nickname: userInfo ? (userInfo.nickName || userInfo.nickname) : undefined,
      avatar: userInfo ? (userInfo.avatarUrl || userInfo.avatar) : undefined
    }),
    workerLogin: (code, userInfo) => http.post('/api/auth/worker-login', {
      code,
      nickname: userInfo ? (userInfo.nickName || userInfo.nickname) : undefined,
      avatar: userInfo ? (userInfo.avatarUrl || userInfo.avatar) : undefined
    }),
    me:         () => http.get('/api/auth/me'),
    workerMe:   () => http.get('/api/auth/worker/me'),
    submitCertification: (data) => http.post('/api/auth/worker/certification', data),
    updateProfile: (data) => http.put('/api/auth/profile', data),
    bindPhone:  (phone, verificationCode) => http.post('/api/auth/bind-phone', {
      phone,
      verification_code: verificationCode
    }),
    switchRole: (role) => http.post('/api/auth/switch-role', { role }),
    logout:     () => http.post('/api/auth/logout'),
    // 地址
    getAddresses:    () => http.get('/api/auth/addresses'),
    addAddress:      (addr) => http.post('/api/auth/addresses', addr),
    updateAddress:   (id, addr) => http.put('/api/auth/addresses/' + id, addr),
    deleteAddress:   (id) => http.del('/api/auth/addresses/' + id),
    setDefaultAddress: (id) => http.put('/api/auth/addresses/' + id + '/default')
  },

  // ==================== 服务类型 ====================
  services: {
    list:     () => http.get('/api/services'),
    detail:   (keyOrId) => http.get('/api/services/' + keyOrId),
    categories: () => http.get('/api/services/categories'),
    search:   (keyword) => http.get('/api/services/search', { keyword }),
    hotTags:  () => http.get('/api/services/hot-tags'),
    platformStats: () => http.get('/api/services/platform-stats'),
    workers:  () => http.get('/api/services/workers/recommend'),
    workerDetail: (id) => http.get('/api/services/workers/' + id)
  },

  // ==================== 订单 ====================
  orders: {
    create:        (data) => http.post('/api/orders', data),
    list:          (status) => http.get('/api/orders', { status }),
    available:     (params) => http.get('/api/orders/available', params),
    workerList:    (status) => http.get('/api/orders/worker', { status }),
    detail:        (id) => http.get('/api/orders/' + id),
    workerDetail:  (id) => http.get('/api/orders/worker/' + id),
    // 竞价
    bidding:       (orderId, data) => http.post('/api/orders/' + orderId + '/bidding', data),
    listBiddings:  (orderId) => http.get('/api/orders/' + orderId + '/biddings'),
    selectBidding: (orderId, biddingId) => http.post('/api/orders/' + orderId + '/select', { bidding_id: biddingId }),
    // 状态
    updateStatus:  (id, status, extra) => http.put('/api/orders/' + id + '/status', Object.assign({ status }, extra || {})),
    cancel:        (id, reason) => http.put('/api/orders/' + id + '/status', { status: 'cancelled', cancel_reason: reason || '' }),
    // 评价
    review:        (id, data) => http.post('/api/orders/' + id + '/review', data)
  },

  // ==================== 评价 ====================
  reviews: {
    list:        (params) => http.get('/api/reviews', params),
    stats:       () => http.get('/api/reviews/stats'),
    // 后端 WorkerReplyRequest 期望 { reply }，URL 不变
    reply:       (reviewId, content) => http.post('/api/reviews/' + reviewId + '/reply', { reply: content }),
    like:        (reviewId) => http.post('/api/reviews/' + reviewId + '/like'),
    mine:        (params) => http.get('/api/reviews/mine', params),
    workerDetail: (workerId, params) => http.get('/api/reviews/worker/' + workerId + '/detail', params)
  },

  // ==================== 收藏 ====================
  favorite: {
    toggleWorker:    (workerId) => http.post('/api/favorite/worker/' + workerId),
    listWorkers:     () => http.get('/api/favorite/workers'),
    existsWorker:    (workerId) => http.get('/api/favorite/workers/exists/' + workerId),
    getWorker:       (workerId) => http.get('/api/favorite/workers/' + workerId)
  },

  // ==================== 钱包 / 交易 ====================
  wallet: {
    detail:       () => http.get('/api/wallet'),
    transactions: (params) => http.get('/api/wallet/transactions', params),
    recharge:     (amount) => http.post('/api/wallet/recharge', { amount }),
    withdraw:     (amount) => http.post('/api/wallet/withdraw', { amount }),
    pay:          (data) => http.post('/api/wallet/pay', data),
    refund:       (data) => http.post('/api/wallet/refund', data),
    offlineConfirm: (orderNo) => http.post('/api/wallet/offline/confirm', { order_no: orderNo })
  },

  // ==================== 微信支付 ====================
  wxpay: {
    rechargeJsapi: (amount) => http.post('/api/wxpay/recharge/jsapi', { amount }),
    orderJsapi:    (orderNo, couponId) => http.post('/api/wxpay/order/jsapi', {
      order_no: orderNo,
      coupon_id: couponId
    })
  },

  // ==================== 优惠券 ====================
  coupon: {
    templates:  () => http.get('/api/coupons/templates'),
    claim:      (templateId) => http.post('/api/coupons/claim/' + templateId),
    mine:       (status) => http.get('/api/coupons/mine', { status }),
    available:  (params) => http.get('/api/coupons/available', params)
  },

  // ==================== 文件上传 ====================
  upload: {
    image:    (filePath) => http.uploadFile({ url: '/api/upload/image', filePath, name: 'file' }),
    certificateImage: (filePath) => http.uploadFile({
      url: '/api/upload/image?category=certificate',
      filePath,
      name: 'file'
    }),
    images:   (filePath) => http.uploadFile({ url: '/api/upload/images', filePath, name: 'files' }),
    delete:   (url) => http.del('/api/upload/file', { url }),
    ossPolicy: () => http.get('/api/upload/oss-policy')
  },

  // ==================== 消息中心 ====================
  messages: {
    list:        () => http.get('/api/messages'),
    unreadCount: () => http.get('/api/messages/unread-count'),
    markRead:    (msgId) => http.put('/api/messages/' + msgId + '/read'),
    markAllRead: () => http.put('/api/messages/read-all'),
    remove:      (msgId) => http.del('/api/messages/' + msgId)
  },

  // ==================== AI 智能助手 ====================
  ai: {
    analyze:         (data) => http.post('/api/ai/analyze', data),
    chat:            (data) => http.post('/api/ai/chat', data),
    estimate:        (data) => http.post('/api/ai/estimate', data),
    quickQuestions:   () => http.get('/api/ai/quick-questions')
  },

  // ==================== 会员中心 ====================
  member: {
    detail:   () => http.get('/api/member'),
    benefits: () => http.get('/api/member/benefits'),
    addGrowth: (amount) => http.post('/api/member/test/add-growth', { amount })
  },

  // ==================== 积分 ====================
  points: {
    detail:       () => http.get('/api/points'),
    logs:         (params) => http.get('/api/points/logs', params),
    signin:       () => http.post('/api/points/signin'),
    exchangeCoupon: (templateId) => http.post('/api/points/exchange/coupon', { coupon_template_id: templateId })
  },

  // ==================== 意见反馈 ====================
  feedback: {
    create: (data) => http.post('/api/feedback', data),
    mine:   (params) => http.get('/api/feedback/mine', params),
    update: (id, data) => http.put('/api/feedback/' + id, data)
  },

  // ==================== 内容页 / FAQ ====================
  pages: {
    faqs:       () => http.get('/api/faqs'),
    agreement:  () => http.get('/api/pages/agreement'),
    privacy:    () => http.get('/api/pages/privacy'),
    about:      () => http.get('/api/pages/about'),
    help:       () => http.get('/api/pages/help'),
    byKey:      (key) => http.get('/api/pages/' + key)
  },

  // ==================== 通知设置 ====================
  settings: {
    getNotification:    () => http.get('/api/settings/notification'),
    updateNotification: (data) => http.put('/api/settings/notification', data)
  },

  // ==================== 实时位置追踪（PRD v6.0 核心） ====================
  track: {
    // 师傅端: 上报位置
    report:       (orderId, data) => http.post('/api/worker/location/report', Object.assign({ order_id: orderId }, data)),
    // 师傅端: 出发 / 到达 / 开始服务
    depart:       (orderId) => http.post('/api/worker/orders/' + orderId + '/depart'),
    arrive:       (orderId, data) => http.post('/api/worker/orders/' + orderId + '/arrive', data || undefined),
    startService: (orderId) => http.post('/api/worker/orders/' + orderId + '/start-service'),
    checkin:       (orderId, data) => http.post('/api/worker/orders/' + orderId + '/checkin', data),
    checkinAbnormal: (orderId, data) => http.post('/api/worker/orders/' + orderId + '/checkin-abnormal', data),
    // 用户端: 实时追踪
    tracking:     (orderId) => http.get('/api/orders/' + orderId + '/tracking'),
    routeHistory: (orderId) => http.get('/api/orders/' + orderId + '/route-history'),
    trackInfo:    (orderId) => http.get('/api/orders/' + orderId + '/track')
  },

  // ==================== 额外费用 ====================
  extraFee: {
    create:  (orderId, data) => http.post('/api/worker/orders/' + orderId + '/extra-fee', data),
    list:    (orderId) => http.get('/api/orders/' + orderId + '/extra-fees'),
    approve: (orderId, feeId) => http.put('/api/orders/' + orderId + '/extra-fees/' + feeId + '/approve'),
    reject:  (orderId, feeId, reason) => http.put('/api/orders/' + orderId + '/extra-fees/' + feeId + '/reject', { reason })
  },

  // ==================== 安心保（保险） ====================
  insurance: {
    buy:       (orderId, data) => http.post('/api/insurance/orders/' + orderId + '/buy', data),
    policy:    (orderId) => http.get('/api/insurance/orders/' + orderId + '/policy'),
    claim:     (data) => http.post('/api/insurance/claims', data),
    claims:    () => http.get('/api/insurance/claims')
  },

  // ==================== 师傅保证金 ====================
  deposit: {
    pay:    (amount) => http.post('/api/worker/deposit/pay', { amount }),
    detail: () => http.get('/api/worker/deposit/'),
    refund: () => http.post('/api/worker/deposit/refund')
  },

  // ==================== 家庭年卡 ====================
  annualCard: {
    templates: () => http.get('/api/annual-cards/templates'),
    purchase:  (data) => http.post('/api/annual-cards/purchase', data),
    mine:      () => http.get('/api/annual-cards/my'),
    use:       (data) => http.post('/api/annual-cards/use', data),
    refund:    (cardId) => http.post('/api/annual-cards/' + cardId + '/refund')
  },

  // ==================== 质检回访 ====================
  quality: {
    inspect:         (orderId, data) => http.post('/api/quality/orders/' + orderId + '/inspect', data),
    feedback:         (inspectionId, data) => http.post('/api/quality/inspections/' + inspectionId + '/feedback', data),
    myInspections:    (params) => http.get('/api/quality/inspections/my', params)
  },

  // ==================== 培训考试 ====================
  training: {
    courses:        () => http.get('/api/worker/training/courses'),
    start:          (courseId) => http.post('/api/worker/training/courses/' + courseId + '/start'),
    complete:       (courseId) => http.post('/api/worker/training/courses/' + courseId + '/complete'),
    exam:           (courseId) => http.get('/api/worker/training/courses/' + courseId + '/exam'),
    submitExam:     (courseId, answers) => http.post('/api/worker/training/courses/' + courseId + '/exam/submit', { answers }),
    records:        () => http.get('/api/worker/training/records'),
    stats:          () => http.get('/api/worker/training/stats')
  },

  // ==================== 客服工单 ====================
  ticket: {
    create:  (data) => http.post('/api/support-tickets/', data),
    mine:    (params) => http.get('/api/support-tickets/my', params),
    detail:  (ticketId) => http.get('/api/support-tickets/' + ticketId),
    reply:   (ticketId, content) => http.post('/api/support-tickets/' + ticketId + '/reply', { content })
  },

  // ==================== 动态定价 ====================
  pricing: {
    currentSurcharge: () => http.get('/api/pricing/current-surcharge'),
    calculate:        (data) => http.post('/api/pricing/calculate', data)
  },

  // ==================== 地图服务 ====================
  map: {
    distance:       (params) => http.get('/api/map/distance', params),
    reverseGeocode: (lat, lng) => http.get('/api/map/reverse-geocode', { lat, lng }),
    geocode:        (address) => http.get('/api/map/geocode', { address }),
    config:         () => http.get('/api/map/config')
  },

  // ==================== 短信 ====================
  sms: {
    sendCode:   (phone) => http.post('/api/sms/send-code', { phone }),
    verifyCode: (phone, code) => http.post('/api/sms/verify-code', { phone, code })
  }
}

// ===== 兼容层：旧版扁平 API 调用，便于现有页面无改动运行 =====
// 新页面请使用命名空间风格: api.orders.list()
const api = module.exports
Object.assign(api, {
  // 服务
  getServices:        () => api.services.list(),
  getServiceDetail:   (key) => api.services.detail(key),
  getCategories:       () => api.services.categories(),
  getPlatformStats:    () => api.services.platformStats(),
  // 师傅
  getWorkers:         () => api.services.workers(),
  getWorkerDetail:     (id) => api.services.workerDetail(id),
  // 客户端订单
  getClientOrders:    (status) => api.orders.list(status),
  getOrderDetail:      (id) => api.orders.detail(id),
  getQuotes:           (orderId) => api.orders.listBiddings(orderId),
  publishOrder:        (data) => api.orders.create(data),
  selectQuote:         (orderId, quoteId) => api.orders.selectBidding(orderId, quoteId),
  cancelOrder:         (orderId) => api.orders.cancel(orderId),
  // 师傅端订单
  getWorkerOrders:     (status) => api.orders.workerList(status),
  getWorkerOrderDetail:(id) => api.orders.workerDetail(id),
  acceptOrder:         (id, price) => api.orders.bidding(id, { price }),
  submitQuote:         (orderId, data) => api.orders.bidding(orderId, data),
  updateOrderStep:     (orderId, step, extra) => {
    const stepMap = { depart: 'depart', arrive: 'arrive', start_service: 'start-service' }
    const fnName = stepMap[step] || step
    if (api.track[fnName]) return api.track[fnName](orderId)
    return api.orders.updateStatus(orderId, step, extra)
  },
  // 地址
  getAddresses:        () => api.auth.getAddresses(),
  addAddress:          (addr) => api.auth.addAddress(addr),
  // 钱包
  getWorkerWallet:     () => api.wallet.detail(),
  withdraw:            (amount) => api.wallet.withdraw(amount),
  getTransactions:     (params) => api.wallet.transactions(params),
  // 用户
  getUserInfo:         () => api.auth.me(),
  getWorkerInfo:       () => api.auth.workerMe(),
  // 优惠券
  getCoupons:          (status) => api.coupon.mine(status),
  // 搜索
  search:              (keyword) => api.services.search(keyword),
  getHotTags:          () => api.services.hotTags()
})

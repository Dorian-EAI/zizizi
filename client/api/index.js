const { get, post, put, del } = require('../utils/request')

module.exports = {
  // ========== 家庭年卡 ==========
  annualCard: {
    templates: () => get('/api/annual-cards/templates'),
    purchase: (data) => post('/api/annual-cards/purchase', data),
    myCards: (status) => get('/api/annual-cards/my', { status }),
    use: (data) => post('/api/annual-cards/use', data),
    refund: (cardId) => post(`/api/annual-cards/${cardId}/refund`),
  },

  // ========== 质检回访 ==========
  quality: {
    feedback: (inspectionId, data) => post(`/api/quality/inspections/${inspectionId}/feedback`, data),
    myInspections: (status) => get('/api/quality/inspections/my', { status }),
  },

  // ========== 培训考试 ==========
  training: {
    courses: (category) => get('/api/worker/training/courses', { category }),
    start: (courseId) => post(`/api/worker/training/courses/${courseId}/start`),
    complete: (courseId) => post(`/api/worker/training/courses/${courseId}/complete`),
    examQuestions: (courseId) => get(`/api/worker/training/courses/${courseId}/exam`),
    submitExam: (courseId, data) => post(`/api/worker/training/courses/${courseId}/exam/submit`, data),
    records: () => get('/api/worker/training/records'),
    stats: () => get('/api/worker/training/stats'),
  },

  // ========== 客服工单 ==========
  ticket: {
    create: (data) => post('/api/support-tickets/', data),
    myTickets: (status) => get('/api/support-tickets/my', { status }),
    detail: (ticketId) => get(`/api/support-tickets/${ticketId}`),
    reply: (ticketId, data) => post(`/api/support-tickets/${ticketId}/reply`, data),
  },

  // ========== 动态定价 ==========
  pricing: {
    currentSurcharge: () => get('/api/pricing/current-surcharge'),
    calculate: (data) => post('/api/pricing/calculate', data),
  },

  // ========== 安心保 ==========
  insurance: {
    buy: (orderId, data) => post(`/api/insurance/orders/${orderId}/buy`, data),
    getPolicy: (orderId) => get(`/api/insurance/orders/${orderId}/policy`),
    submitClaim: (data) => post('/api/insurance/claims', data),
    myClaims: (status) => get('/api/insurance/claims', { status }),
  },

  // ========== 保证金 ==========
  deposit: {
    pay: (data) => post('/api/worker/deposit/pay', data),
    detail: () => get('/api/worker/deposit/'),
    refund: () => post('/api/worker/deposit/refund'),
  },

  // ========== LBS 轨迹 ==========
  lbsTrack: {
    checkIn: (data) => post('/api/lbs-track/checkin', data),
    getTrack: (orderId) => get(`/api/lbs-track/orders/${orderId}/track`),
  },

  // ========== 补差价 ==========
  extraFee: {
    apply: (data) => post('/api/extra-fees/apply', data),
    approve: (feeId) => post(`/api/extra-fees/${feeId}/approve`),
    reject: (feeId) => post(`/api/extra-fees/${feeId}/reject`),
  },
}

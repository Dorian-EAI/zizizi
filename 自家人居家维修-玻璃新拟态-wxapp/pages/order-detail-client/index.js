// pages/order-detail-client/index.js — 客户端订单详情
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { STATUS_TEXT } = require('../../utils/order-status')
const { requestPayment, isPaymentCancelled } = require('../../utils/wx-payment')

// 状态文案映射
const STATUS_TITLE = {
  pending: '等待师傅接单',
  bidding: '师傅正在报价',
  accepted: '师傅已接单',
  departing: '师傅正在赶来',
  arrived: '师傅已到达',
  serving: '师傅正在服务',
  completed: '服务已完成',
  paid: '待您评价',
  reviewed: '订单已完成',
  pending_review: '待您评价',
  canceled: '订单已取消',
  closed: '订单已关闭'
}

const STATUS_SUB = {
  pending: '请稍候，附近师傅将陆续报价',
  bidding: '请选择合适的师傅报价',
  accepted: '师傅待出发，可先电话沟通',
  departing: '可实时查看师傅位置和预计到达时间',
  arrived: '师傅已到达，请保持电话畅通',
  serving: '如有问题请联系师傅',
  completed: '请确认费用并完成支付',
  paid: '请对本次服务进行评价',
  reviewed: '感谢您的使用',
  pending_review: '请对本次服务进行评价',
  canceled: '订单已取消，如需服务可重新发布',
  closed: '订单已关闭'
}

const PRIMARY_ACTION = {
  pending: '查看详情',
  bidding: '刷新报价',
  accepted: '联系师傅',
  departing: '查看实时位置',
  arrived: '联系师傅',
  serving: '联系师傅',
  completed: '去支付',
  paid: '去评价',
  reviewed: '查看详情',
  pending_review: '去评价'
}

Page({
  data: {
    statusBarHeight: 20,
    orderId: '',
    order: {},
    quotes: [],
    workerAvatarUrl: '',
    // 横向进度时间轴节点（4 段：已接单/已出发/服务中/待验收）
    timelineNodes: [],
    timelineProgress: 0,
    // 服务轨迹（LBS）
    tracks: [],
    // 师傅评价气泡
    reviewBubbles: [],
    statusTitle: '',
    statusSub: '',
    primaryActionText: '',
    paymentSubmitting: false,
    icons: {}
  },

  onLoad(query) {
    const id = query && query.id
    this.setData({
      orderId: id,
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        more: buildIcon('list', COLORS.text1),
        location: buildIcon('location', COLORS.brand),
        clock: buildIcon('clock', COLORS.brand),
        orders: buildIcon('orders', COLORS.brand),
        timer: buildIcon('timer', COLORS.text3),
        phone: buildIcon('phone', COLORS.brand),
        message: buildIcon('message', COLORS.accentDark || '#A0723C'),
        check: buildIcon('check', '#FFFFFF'),
        shield: buildIcon('shield', COLORS.brand),
        file: buildIcon('orders', COLORS.brand),
        headset: buildIcon('phone', COLORS.text2)
      }
    })
    this.loadOrder(id)
  },

  onMore() {
    wx.showActionSheet({
      itemList: ['分享订单', '投诉建议', '取消订单'],
      success: (res) => {
        if (res.tapIndex === 2) {
          this.onCancel()
        } else if (res.tapIndex === 1) {
          wx.navigateTo({
            url: '/pages/client-service/index?create=1&orderId=' + this.data.orderId
          })
        }
      }
    })
  },

  onContactService() {
    wx.showToast({ title: '正在接入客服', icon: 'none' })
  },

  async onClaim() {
    if (!this.data.orderId) return
    wx.showLoading({ title: '查询保单', mask: true })
    try {
      const api = app.getApi()
      const policy = await api.insurance.policy(this.data.orderId)
      wx.hideLoading()
      if (!policy || !policy.id) {
        wx.showToast({ title: '当前订单暂无可理赔保单', icon: 'none' })
        return
      }
      wx.navigateTo({
        url: '/pages/client-insurance-claim/index?orderId=' + this.data.orderId +
          '&policyId=' + policy.id +
          '&orderNo=' + encodeURIComponent(this.data.order.orderNo || '')
      })
    } catch (error) {
      wx.hideLoading()
      console.error('查询保单失败', error)
    }
  },

  async loadOrder(id) {
    const api = app.getApi()
    try {
      const order = await api.getOrderDetail(id)
      // 后端 OrderResponse 为 snake_case(order_no/service_name/service_type)，前端读取 camelCase，需别名
      const withIcon = Object.assign({}, order, {
        orderNo: order.order_no != null ? order.order_no : order.orderNo,
        serviceName: order.service_name != null ? order.service_name : order.serviceName,
        serviceKey: order.service_type != null ? order.service_type : order.serviceKey,
        workerPhone: order.worker_phone != null ? order.worker_phone : (order.workerPhone || ''),
        iconUrl: buildIcon(order.icon, COLORS.brand),
        statusText: order.statusText || STATUS_TEXT[order.status] || '',
        etaText: order.etaText || (order.eta ? '预计 ' + order.eta + ' 完成' : ''),
        visitFeeFree: Boolean(order.visitFeeFree || order.visit_fee_free),
        insurance: order.insurance || null,
        supplement: order.supplement || null
      })
      // 横向进度时间轴节点 + 进度百分比
      const timelineNodes = this.buildTimelineNodes(order.status, order)
      const timelineProgress = this.calcTimelineProgress(order.status)
      // 服务轨迹（LBS）
      const tracks = this.buildTracks(order.tracks)
      // 师傅评价气泡（仅 paid / reviewed 显示）
      const reviewBubbles = Array.isArray(order.reviewBubbles)
        ? order.reviewBubbles
        : (Array.isArray(order.review_bubbles) ? order.review_bubbles : [])
      this.setData({
        order: withIcon,
        statusTitle: STATUS_TITLE[order.status] || '',
        statusSub: STATUS_SUB[order.status] || '',
        primaryActionText: PRIMARY_ACTION[order.status] || '',
        timelineNodes,
        timelineProgress,
        tracks,
        reviewBubbles,
        workerAvatarUrl: buildIcon('user', '#0D9488')
      })
      // 竞价中：加载报价
      if (order.status === 'bidding') {
        this.loadQuotes(id)
      }
    } catch (e) {
      console.error('加载订单详情失败', e)
    }
  },

  // 构建横向进度时间轴节点（已接单/已出发/服务中/待验收）
  buildTimelineNodes(status, order) {
    const steps = order.steps || {}
    const nodes = [
      { key: 'accept', label: '已接单', time: steps.accept || this.formatDateTime(order.accepted_at) },
      { key: 'depart', label: '已出发', time: steps.depart || this.formatDateTime(order.departed_at) },
      { key: 'serve', label: '服务中', time: steps.serve || this.formatDateTime(order.started_at) },
      { key: 'verify', label: '待验收', time: steps.verify || this.formatDateTime(order.completed_at) }
    ]
    const stateMap = {
      accepted:    { done: ['accept'], active: 'depart' },
      departing:   { done: ['accept', 'depart'], active: 'serve' },
      arrived:     { done: ['accept', 'depart'], active: 'serve' },
      serving:     { done: ['accept', 'depart', 'serve'], active: '' },
      completed:   { done: ['accept', 'depart', 'serve'], active: 'verify' },
      paid:        { done: ['accept', 'depart', 'serve', 'verify'], active: '' },
      pending_review: { done: ['accept', 'depart', 'serve', 'verify'], active: '' },
      reviewed:    { done: ['accept', 'depart', 'serve', 'verify'], active: '' }
    }
    const cfg = stateMap[status] || { done: [], active: '' }
    return nodes.map(n => ({
      key: n.key,
      label: n.label,
      time: n.time,
      state: cfg.done.indexOf(n.key) >= 0 ? 'done' : (cfg.active === n.key ? 'active' : 'pending')
    }))
  },

  calcTimelineProgress(status) {
    const progressMap = {
      accepted: 25, departing: 50, arrived: 50, serving: 75,
      completed: 75, paid: 100, pending_review: 100, reviewed: 100
    }
    return progressMap[status] || 0
  },

  // 构建服务轨迹（LBS）
  buildTracks(tracks) {
    if (!Array.isArray(tracks)) return []
    return tracks.map(item => Object.assign({}, item, {
      time: this.formatDateTime(item.time || item.created_at)
    }))
  },

  formatDateTime(value) {
    if (!value) return ''
    const text = String(value).replace('T', ' ')
    return text.length > 16 ? text.slice(0, 16) : text
  },

  async loadQuotes(orderId) {
    const api = app.getApi()
    try {
      const quotes = await api.getQuotes(orderId)
      // 后端竞价项返回 worker_name/worker_avatar/worker_rating(snake)，前端读取 camelCase
      const withIcons = (quotes || []).map(q => Object.assign({}, q, {
        workerName: q.worker_name != null ? q.worker_name : q.workerName,
        workerAvatar: q.worker_avatar != null ? q.worker_avatar : q.workerAvatar,
        rating: q.worker_rating != null ? q.worker_rating : q.rating,
        avatarUrl: buildIcon('user', '#6B8F71')
      }))
      this.setData({ quotes: withIcons })
    } catch (e) {
      console.error('加载报价失败', e)
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  // 点击报价卡（查看师傅详情）
  onQuoteTap(e) {
    const id = e.currentTarget.dataset.id
    wx.showToast({ title: '查看师傅详情', icon: 'none' })
  },

  // 接受报价
  async onAcceptQuote(e) {
    const id = e.currentTarget.dataset.id
    const quote = this.data.quotes.find(q => q.id === id)
    if (!quote) return
    wx.showModal({
      title: '确认选择',
      content: `选择 ${quote.workerName} 师傅？报价 ¥${quote.price}`,
      confirmColor: '#0D9488',
      success: async (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '处理中...' })
        const api = app.getApi()
        try {
          await api.orders.selectBidding(this.data.orderId, quote.id)
          wx.hideLoading()
          wx.showToast({ title: '已选定师傅', icon: 'success' })
          setTimeout(() => this.loadOrder(this.data.orderId), 800)
        } catch (e) {
          wx.hideLoading()
          wx.showToast({ title: '操作失败', icon: 'none' })
        }
      }
    })
  },

  onChat() {
    wx.navigateTo({ url: '/pages/client-chat/index' })
  },

  onCall() {
    const phone = String(this.data.order.workerPhone || '').trim()
    const digits = phone.replace(/\D/g, '')
    if (!phone || phone.indexOf('*') >= 0 || !/^\+?[0-9][0-9() -]{5,18}[0-9]$/.test(phone) || digits.length < 7 || digits.length > 15) {
      wx.showToast({ title: '联系方式暂不可用', icon: 'none' })
      return
    }
    wx.makePhoneCall({ phoneNumber: phone })
  },

  // 跳转到报价列表页
  onViewQuotes() {
    wx.navigateTo({
      url: '/pages/client-quote-list/index?orderId=' + this.data.orderId +
           '&orderNo=' + (this.data.order.orderNo || '') +
           '&serviceName=' + (this.data.order.serviceName || '')
    })
  },

  // 跳转到实时追踪页
  onTrackWorker() {
    wx.navigateTo({ url: '/pages/client-order-tracking/index?orderId=' + this.data.orderId })
  },

  onCancel() {
    if (this.data.order.status === 'pending_review') {
      wx.navigateBack({ delta: 1 })
      return
    }
    wx.showModal({
      title: '取消订单',
      content: '确认取消该订单？取消后无法恢复',
      confirmColor: '#DC2626',
      success: async (res) => {
        if (!res.confirm) return
        wx.showLoading({ title: '取消中...' })
        const api = app.getApi()
        try {
          await api.cancelOrder(this.data.orderId)
          wx.hideLoading()
          wx.showToast({ title: '已取消', icon: 'success' })
          setTimeout(() => wx.navigateBack({ delta: 1 }), 800)
        } catch (e) {
          wx.hideLoading()
        }
      }
    })
  },

  onPrimaryAction() {
    const status = this.data.order.status
    if (status === 'bidding') {
      // 跳报价列表
      this.onViewQuotes()
    } else if (status === 'departing') {
      // 服务中或师傅出发/到达 → 可查看实时位置
      this.onTrackWorker()
    } else if (status === 'accepted' || status === 'arrived' || status === 'serving') {
      this.onCall()
    } else if (status === 'completed') {
      this.onPayOrder()
    } else if (status === 'pending_review') {
      // 跳评价 — 暂用页面内 modal（如有 review 页可改为跳转）
      wx.showToast({ title: '请在订单完成后于详情页评价', icon: 'none' })
    } else if (status === 'paid') {
      wx.showToast({ title: '请对本次服务评价', icon: 'none' })
    }
  },

  onPayOrder() {
    if (this.data.paymentSubmitting) return
    const order = this.data.order || {}
    const amount = order.final_price != null
      ? order.final_price
      : (order.finalPrice != null ? order.finalPrice : (order.budget || 0))
    wx.showModal({
      title: '确认支付',
      content: '订单 ' + (order.orderNo || '') + '，应付 ¥' + Number(amount || 0).toFixed(2),
      confirmText: '微信支付',
      confirmColor: '#0D9488',
      success: async result => {
        if (!result.confirm) return
        if (!order.orderNo) {
          wx.showToast({ title: '订单编号缺失，无法支付', icon: 'none' })
          return
        }

        this.setData({ paymentSubmitting: true })
        wx.showLoading({ title: '发起支付', mask: true })
        try {
          const api = app.getApi()
          const payParams = await api.wxpay.orderJsapi(order.orderNo)
          await requestPayment(payParams)
          wx.hideLoading()
          wx.showToast({ title: '支付已提交', icon: 'success' })
          // 订单最终状态以微信异步回调和服务端查询结果为准。
          setTimeout(() => this.loadOrder(this.data.orderId), 1200)
        } catch (error) {
          wx.hideLoading()
          console.error('订单支付失败', error)
          if (isPaymentCancelled(error)) {
            wx.showToast({ title: '已取消支付', icon: 'none' })
          } else if (!error || error.code !== 'AUTH_REQUIRED') {
            wx.showToast({ title: (error && error.message) || '支付失败，请重试', icon: 'none' })
          }
        } finally {
          this.setData({ paymentSubmitting: false })
        }
      }
    })
  },

  // 提交评价（页面内 modal）
  async onSubmitReview(e) {
    const { rating, content, tags } = e.currentTarget.dataset
    if (!rating || rating < 1) {
      wx.showToast({ title: '请选择评分', icon: 'none' })
      return
    }
    wx.showLoading({ title: '提交中...' })
    const api = app.getApi()
    try {
      await api.orders.review(this.data.orderId, { rating, content, tags })
      wx.hideLoading()
      wx.showToast({ title: '评价成功', icon: 'success' })
      setTimeout(() => this.loadOrder(this.data.orderId), 800)
    } catch (e) {
      wx.hideLoading()
    }
  }
})

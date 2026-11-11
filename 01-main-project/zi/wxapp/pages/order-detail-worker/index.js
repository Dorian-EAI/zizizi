// pages/order-detail-worker/index.js — 师傅端订单详情
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')
const { STATUS_TEXT } = require('../../utils/order-status')

// 状态标题/副标题
const STATUS_TITLE = {
  available: '可抢订单',
  accepted: '已接单 · 待出发',
  departing: '位置上报中',
  arrived: '已到达现场',
  serving: '服务进行中',
  completed: '订单已完成'
}

const STATUS_SUB = {
  available: '请尽快提交报价，抢占订单',
  accepted: '点击出发后将开始位置上报',
  departing: '前往客户途中，位置实时同步',
  arrived: '请确认后开始服务',
  serving: '请按服务流程规范作业',
  completed: '感谢您的辛勤服务'
}

// 服务中步骤：arrived / diagnosing / repairing / done（与 worker-orders STEP_TEXT 保持一致）
const STEP_TITLES = [
  { key: 'arrived',    title: '已到达' },
  { key: 'diagnosing', title: '检测中' },
  { key: 'repairing',  title: '维修中' },
  { key: 'done',       title: '待验收' }
]

// 下一步文案
const NEXT_STEP_TEXT = {
  arrived: '开始检测',
  diagnosing: '开始维修',
  repairing: '完成服务',
  done: '提交完成'
}

// 水平 Timeline 节点（已接单 → 已联系 → 待服务 → 已完成）
const TIMELINE_NODES = [
  { key: 'accepted', label: '已接单' },
  { key: 'contacted', label: '已联系' },
  { key: 'serving', label: '待服务' },
  { key: 'completed', label: '已完成' }
]

// 状态 → timeline 进度索引（-1 表示不显示 timeline）
const STATUS_PROGRESS = {
  available: -1,
  accepted: 0,
  departing: 1,
  arrived: 2,
  serving: 2,
  completed: 3
}

// 垂直签到步骤定义
const CHECKIN_STEPS = [
  { key: 'depart', title: '前往服务', action: '点击出发后开始位置上报' },
  { key: 'arrive', title: '到达签到', action: '到达客户附近，GPS 自动签到' },
  { key: 'start', title: '开工签到', action: '上传现场开工照片' },
  { key: 'complete', title: '完工签到', action: '上传现场完工照片，完成服务签到' }
]

Page({
  data: {
    statusBarHeight: 20,
    orderId: '',
    order: {},
    steps: [],
    statusTitle: '',
    statusSub: '',
    nextStepText: '',
    myQuote: '',
    myEta: '',
    etaOptions: ['30分钟', '45分钟', '1小时', '2小时'],
    customerAvatarUrl: '',
    timeline: [],
    timelineFill: 0,
    checkin: [],
    extraFeeRecord: null,
    icons: {},
    navScrolled: false
  },

  onLoad(query) {
    const id = query && query.id
    this.setData({
      orderId: id,
      statusBarHeight: app.globalData.statusBarHeight || 20,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        location: buildIcon('location', COLORS.text3),
        calendar: buildIcon('calendar', COLORS.text3),
        clock: buildIcon('clock', COLORS.brandWorker),
        wallet: buildIcon('wallet', COLORS.brandWorker),
        phone: buildIcon('phone', '#FFFFFF'),
        message: buildIcon('message', COLORS.brandWorker),
        check: buildIcon('check', '#FFFFFF'),
        upload: buildIcon('upload', '#FFFFFF'),
        alertTriangle: buildIcon('alertTriangle', COLORS.accentDark),
        plus: buildIcon('plus', COLORS.brandWorker),
        camera: buildIcon('camera', '#FFFFFF'),
        shield: buildIcon('shield', '#FFFFFF')
      }
    })
    this.loadOrder(id)
  },

  async loadOrder(id) {
    const api = app.getApi()
    try {
      // 后端无 /api/orders/worker/{id} 路由（会 404）；
      // 通用详情 /api/orders/{id} 对师傅开放（归属校验）。
      // 但 pending(可抢)订单 worker_id 为空，通用详情会 403，需降级到 available 列表查找。
      let raw = null
      try {
        raw = await api.orders.detail(id)
      } catch (e1) {
        // 403/404 时降级：从可抢订单列表中按 id 查找（pending 订单）
        try {
          const all = await api.orders.available({})
          raw = (all || []).find(function (o) { return String(o.id) === String(id) }) || null
        } catch (e2) {
          raw = null
        }
      }
      const order = this.mapOrder(raw || {})
      const withIcon = Object.assign({}, order, {
        iconUrl: buildIcon(order.icon || 'orders', COLORS.brandWorker),
        statusText: STATUS_TEXT[order.status] || order.statusText || ''
      })
      const tl = this.buildTimeline(order.status)
      this.setData({
        order: withIcon,
        statusTitle: STATUS_TITLE[order.status] || '',
        statusSub: STATUS_SUB[order.status] || '',
        nextStepText: NEXT_STEP_TEXT[order.step] || '下一步',
        steps: this.buildSteps(order.step),
        customerAvatarUrl: buildIcon('user', '#6B8F71'),
        timeline: tl.timeline,
        timelineFill: tl.timelineFill,
        checkin: this.buildCheckin(order.status),
        extraFeeRecord: order.extraFeeRecord || null
      })
    } catch (e) {
      console.error('加载师傅订单详情失败', e)
    }
  },

  // 后端 OrderResponse(snake_case) → 前端 wxml 期望(camelCase)
  mapOrder(raw) {
    if (!raw) return {}
    const addr = this.parseAddress(raw.address)
    // 服务中子步骤：后端不持久化 diagnosing/repairing，按状态推导默认值
    let step = raw.step
    if (!step) {
      if (raw.status === 'arrived') step = 'arrived'
      else if (raw.status === 'serving') step = 'repairing'
    }
    return Object.assign({}, raw, {
      serviceName: raw.serviceName || raw.service_name || '',
      serviceType: raw.serviceType || raw.service_type || '',
      finalPrice: raw.finalPrice != null ? raw.finalPrice : raw.final_price,
      // "我的报价"展示：优先 final_price，其次 budget
      price: raw.price != null ? raw.price : (raw.final_price != null ? raw.final_price : raw.budget),
      time: raw.time || this.formatDate(raw.appoint_time),
      createdAt: raw.createdAt || this.formatDate(raw.created_at),
      address: addr.address,
      lat: raw.lat != null ? raw.lat : addr.lat,
      lng: raw.lng != null ? raw.lng : addr.lng,
      step: step,
      icon: raw.icon || 'orders',
      userName: raw.userName || raw.user_name || '',
      userPhone: raw.userPhone || raw.user_phone || ''
    })
  },

  // 解析后端 address 字段（JSON {address,latitude,longitude} 或纯文本）
  parseAddress(addrStr) {
    if (!addrStr) return { address: '', lat: null, lng: null }
    if (typeof addrStr === 'object') {
      return {
        address: addrStr.address || '',
        lat: addrStr.latitude != null ? addrStr.latitude : (addrStr.lat || null),
        lng: addrStr.longitude != null ? addrStr.longitude : (addrStr.lng || null)
      }
    }
    const s = String(addrStr)
    try {
      const obj = JSON.parse(s)
      if (obj && typeof obj === 'object') {
        return {
          address: obj.address || '',
          lat: obj.latitude != null ? obj.latitude : (obj.lat || null),
          lng: obj.longitude != null ? obj.longitude : (obj.lng || null)
        }
      }
    } catch (e) {}
    return { address: s, lat: null, lng: null }
  },

  formatDate(dt) {
    if (!dt) return ''
    const s = String(dt).replace('T', ' ')
    return s.length > 16 ? s.slice(0, 16) : s
  },

  // 构建服务进度步骤
  buildSteps(currentStep) {
    const idx = STEP_TITLES.findIndex(s => s.key === currentStep)
    return STEP_TITLES.map((s, i) => ({
      key: s.key,
      title: s.title,
      done: i < idx,
      active: i === idx
    }))
  },

  // 构建水平 Timeline（已接单 → 已联系 → 待服务 → 已完成）
  buildTimeline(status) {
    const prog = STATUS_PROGRESS[status]
    if (prog < 0) return { timeline: [], timelineFill: 0 }
    const timeline = TIMELINE_NODES.map((n, i) => {
      let state = 'pending'
      if (status === 'completed' || i < prog) state = 'done'
      else if (i === prog) state = 'active'
      return { key: n.key, label: n.label, state, time: '' }
    })
    let timelineFill = 0
    if (status === 'completed') {
      timelineFill = 100
    } else if (prog >= 0) {
      timelineFill = Math.round((prog / (TIMELINE_NODES.length - 1)) * 100)
    }
    return { timeline, timelineFill }
  },

  // 构建垂直签到步骤（前往服务 / 到达签到 / 开工签到 / 完工签到）
  buildCheckin(status) {
    // 各状态对应的当前步骤索引（-1 表示全部完成）
    const curIdx = {
      accepted: 0,
      departing: 0,
      arrived: 1,
      serving: 3,
      completed: -1
    }[status]
    return CHECKIN_STEPS.map((s, i) => {
      let state = 'pending'
      let statusText = '待签到'
      let meta = '待签到'
      if (curIdx < 0 || i < curIdx) {
        state = 'done'
        statusText = '已完成'
        meta = '已完成'
      } else if (i === curIdx) {
        state = 'current'
        statusText = '进行中'
        meta = s.action
      }
      return { key: s.key, title: s.title, state, statusText, meta }
    })
  },

  // 滚动驱动标题栏变形动画（参考 小程序动画与布局实现规范.md 第二章）
  // 仅在跨阈值时 setData，避免高频更新
  onScroll(e) {
    const scrollTop = e.detail.scrollTop
    const shouldScroll = scrollTop > 40
    if (shouldScroll !== this.data.navScrolled) {
      this.setData({ navScrolled: shouldScroll })
    }
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  },

  // 报价输入
  onQuoteInput(e) {
    this.setData({ myQuote: e.detail.value })
  },

  // 选择 ETA
  onEtaSelect(e) {
    this.setData({ myEta: e.currentTarget.dataset.eta })
  },

  // 提交报价
  async onSubmitQuote() {
    const quote = this.data.myQuote
    const eta = this.data.myEta
    if (!quote || Number(quote) <= 0) {
      wx.showToast({ title: '请输入报价金额', icon: 'none' })
      return
    }
    if (!eta) {
      wx.showToast({ title: '请选择预计到达时间', icon: 'none' })
      return
    }
    wx.showLoading({ title: '提交中...' })
    const api = app.getApi()
    try {
      // 后端 BiddingRequest 期望 { price, message, eta }；兼容层 submitQuote 会丢弃 eta，故直接调 bidding
      await api.orders.bidding(this.data.orderId, { price: Number(quote), eta: eta, message: '' })
      wx.hideLoading()
      wx.showToast({ title: '报价已提交', icon: 'success' })
      setTimeout(() => wx.navigateBack({ delta: 1 }), 1200)
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '提交失败', icon: 'none' })
    }
  },

  // 已接单 → 点击出发，跳转位置上报页
  onDepart() {
    const orderId = this.data.orderId
    wx.navigateTo({
      url: '/package-worker/pages/worker-location-report/index?orderId=' + orderId
    })
  },

  // departing 状态 → 继续位置上报
  onContinueReport() {
    const orderId = this.data.orderId
    wx.navigateTo({
      url: '/package-worker/pages/worker-location-report/index?orderId=' + orderId
    })
  },

  // 已到达 → 开始服务（触发 arrived→serving 切换由位置上报页"我已到达"按钮完成；
  // 若直接在详情页则提供手动确认）
  async onStartService() {
    wx.showLoading({ title: '开始服务...' })
    const api = app.getApi()
    try {
      await api.track.startService(this.data.orderId)
      wx.hideLoading()
      wx.showToast({ title: '已开始服务', icon: 'success' })
      const order = Object.assign({}, this.data.order, { status: 'serving' })
      this.setData({
        order,
        statusTitle: STATUS_TITLE['serving'],
        statusSub: STATUS_SUB['serving']
      })
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  // 服务中：进入下一步
  async onNextStep() {
    const order = this.data.order
    const step = order.step
    if (step === 'arrived') {
      this.updateStep('diagnosing')
    } else if (step === 'diagnosing') {
      this.updateStep('repairing')
    } else if (step === 'repairing') {
      this.updateStep('done')
    } else if (step === 'done') {
      // 完成服务 → 调用完成接口（后端要求 worker 完成时必传 price）
      wx.showLoading({ title: '提交中...' })
      const api = app.getApi()
      try {
        const o = this.data.order
        const completePrice = o.finalPrice != null ? o.finalPrice : (o.price != null ? o.price : (o.budget || 0))
        await api.orders.updateStatus(this.data.orderId, 'completed', { price: completePrice })
        wx.hideLoading()
        wx.showToast({ title: '订单已完成', icon: 'success' })
        setTimeout(() => wx.navigateBack({ delta: 1 }), 1000)
      } catch (e) {
        wx.hideLoading()
        wx.showToast({ title: '提交失败', icon: 'none' })
      }
    }
  },

  async updateStep(step) {
    // diagnosing / repairing 为前端服务进度子步骤，后端 Order.status 不支持这两种值，
    // 仅做本地状态推进，避免调用非法状态更新触发 400。
    if (step === 'diagnosing' || step === 'repairing') {
      const order = Object.assign({}, this.data.order, { step })
      this.setData({
        order,
        steps: this.buildSteps(step),
        nextStepText: NEXT_STEP_TEXT[step] || '下一步'
      })
      return
    }
    wx.showLoading({ title: '更新中...' })
    const api = app.getApi()
    try {
      await api.updateOrderStep(this.data.orderId, step)
      wx.hideLoading()
      const order = Object.assign({}, this.data.order, { step })
      this.setData({
        order,
        steps: this.buildSteps(step),
        nextStepText: NEXT_STEP_TEXT[step] || '下一步'
      })
      wx.showToast({ title: '已更新状态', icon: 'success' })
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '更新失败', icon: 'none' })
    }
  },

  onChat() {
    wx.showToast({ title: 'IM 开发中', icon: 'none' })
  },

  promptExtraFee(title, placeholderText) {
    return new Promise(resolve => {
      wx.showModal({
        title,
        editable: true,
        placeholderText,
        confirmColor: '#2D6CDF',
        success: result => resolve(result.confirm ? String(result.content || '').trim() : '')
      })
    })
  },

  // 申请补差价（serving 状态）：页面内采集必要字段并直接调用现有接口。
  async onApplyExtraFee() {
    const amountText = await this.promptExtraFee('申请补差价', '请输入补差金额（元）')
    if (!amountText) return
    if (!/^\d+(\.\d{1,2})?$/.test(amountText)) {
      wx.showToast({ title: '金额最多保留两位小数', icon: 'none' })
      return
    }
    const amount = Number(amountText)
    const amountCents = Math.round(amount * 100)
    if (!Number.isSafeInteger(amountCents) || amountCents <= 0 || amountCents > 100000000) {
      wx.showToast({ title: '请输入有效补差金额', icon: 'none' })
      return
    }
    const reason = await this.promptExtraFee('补差原因', '例如：现场新增配件')
    if (!reason) return
    if (reason.length < 2 || reason.length > 500) {
      wx.showToast({ title: '补差原因需为2至500字', icon: 'none' })
      return
    }

    wx.showLoading({ title: '提交中', mask: true })
    try {
      const api = app.getApi()
      await api.extraFee.create(this.data.orderId, {
        items: [{ name: reason.slice(0, 50), price: amountCents, unit: '项' }],
        total_amount: amountCents,
        reason,
        photo_urls: []
      })
      wx.hideLoading()
      wx.showToast({ title: '补差申请已提交', icon: 'success' })
      this.loadOrder(this.data.orderId)
    } catch (error) {
      wx.hideLoading()
      console.error('提交补差价失败', error)
    }
  },

  onCall() {
    const phone = String(this.data.order.userPhone || '').trim()
    const digits = phone.replace(/\D/g, '')
    if (!phone || phone.indexOf('*') >= 0 || !/^\+?[0-9][0-9() -]{5,18}[0-9]$/.test(phone) || digits.length < 7 || digits.length > 15) {
      wx.showToast({ title: '联系方式暂不可用', icon: 'none' })
      return
    }
    wx.makePhoneCall({ phoneNumber: phone })
  }
})

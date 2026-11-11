// pages/client-chat/index.js — AI智能助手聊天页 玻璃新拟态
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const CACHE_KEY = 'client_chat_history'

const DEFAULT_QUICK = [
  '如何做防水？',
  '空调不制冷？',
  '怎么选师傅？',
  '退款多久到账？'
]

const QUICK_SERVICES = [
  { key: 'water',      name: '水电维修' },
  { key: 'pipe',       name: '管道疏通' },
  { key: 'appliance',  name: '家电维修' },
  { key: 'door',       name: '门窗维修' }
]

Page({
  data: {
    statusBarHeight: 20,
    messages: [],
    inputValue: '',
    quickQuestions: DEFAULT_QUICK,
    quickServices: QUICK_SERVICES,
    chatTime: '',
    scrollIntoView: '',
    sending: false,
    icons: {}
  },

  onLoad() {
    const now = new Date()
    const pad = (n) => (n < 10 ? '0' + n : '' + n)
    const chatTime = '今天 ' + pad(now.getHours()) + ':' + pad(now.getMinutes())
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      chatTime,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        bot: buildIcon('bot', COLORS.white),
        more: buildIcon('list', COLORS.text1),
        mic: buildIcon('phone', COLORS.brand),
        send: buildIcon('navigation', COLORS.white)
      }
    })
    this.loadHistory()
  },

  loadHistory() {
    // 暂用本地 storage 缓存
    try {
      const cached = wx.getStorageSync(CACHE_KEY)
      if (cached && cached.length) {
        this.setData({ messages: cached })
        this.scrollBottom()
        return
      }
    } catch (e) {}
    // 默认欢迎语
    const welcome = [{
      id: 'm_' + Date.now(),
      role: 'service',
      content: '你好，我是自家人AI助手，描述你的维修问题，我来推荐服务方案。',
      time: this.fmtTime(Date.now())
    }]
    this.setData({ messages: welcome })
    this.saveHistory(welcome)
  },

  saveHistory(messages) {
    try {
      wx.setStorageSync(CACHE_KEY, messages || this.data.messages)
    } catch (e) {}
  },

  fmtTime(ts) {
    const d = new Date(ts)
    const pad = (n) => (n < 10 ? '0' + n : '' + n)
    return pad(d.getHours()) + ':' + pad(d.getMinutes())
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value })
  },

  async onSend() {
    const text = this.data.inputValue.trim()
    if (!text || this.data.sending) return
    await this.sendMessage(text)
    this.setData({ inputValue: '' })
  },

  async onQuickTap(e) {
    const text = e.currentTarget.dataset.text
    if (!text || this.data.sending) return
    await this.sendMessage(text)
  },

  // 快捷服务标签点击：直接发送服务名
  async onQuickService(e) {
    const key = e.currentTarget.dataset.key
    const item = this.data.quickServices.find(s => s.key === key)
    if (!item || this.data.sending) return
    await this.sendMessage('我要咨询' + item.name)
  },

  async sendMessage(text) {
    const userMsg = {
      id: 'm_' + Date.now(),
      role: 'user',
      content: text,
      time: this.fmtTime(Date.now())
    }
    const messages = this.data.messages.concat([userMsg])
    this.setData({ messages, sending: true })
    this.scrollBottom()
    this.saveHistory(messages)

    // 调用 AI 自动回复作为客服响应
    const api = app.getApi()
    try {
      const resp = await api.ai.chat({ message: text })
      const rawReply = typeof resp === 'string'
        ? resp
        : (resp && (resp.text || resp.reply || resp.content || resp.message))
      const reply = typeof rawReply === 'string' ? rawReply.trim() : ''
      if (!reply) throw new Error('AI 服务未返回有效回复')
      const recSource = resp && (resp.recommendation || (resp.estimate ? this._estimateToRec(resp.estimate) : null))
      const serviceMsg = {
        id: 'm_' + Date.now() + '_s',
        role: 'service',
        content: reply,
        time: this.fmtTime(Date.now()),
        rec: recSource ? this.buildRec(recSource) : null
      }
      const newMessages = this.data.messages.concat([serviceMsg])
      this.setData({ messages: newMessages, sending: false })
      this.scrollBottom()
      this.saveHistory(newMessages)
    } catch (e) {
      console.error('AI 回复失败', e)
      const errMsg = {
        id: 'm_' + Date.now() + '_e',
        role: 'service',
        content: '网络开小差了，请稍后重试。',
        time: this.fmtTime(Date.now())
      }
      const newMessages = this.data.messages.concat([errMsg])
      this.setData({ messages: newMessages, sending: false })
      this.scrollBottom()
      this.saveHistory(newMessages)
    }
  },

  // 将后端估价结果（estimate）转为推荐卡数据
  _estimateToRec(est) {
    if (!est) return null
    return {
      id: est.service_type || est.id,
      key: est.service_type || est.key,
      name: est.service_name || est.name || '推荐服务',
      price: est.suggested_price != null ? est.suggested_price : est.min_price,
      duration: est.estimated_minutes != null ? est.estimated_minutes : est.duration
    }
  },

  // 构造推荐卡数据
  buildRec(rec) {
    if (!rec) return null
    const iconMap = {
      pipe: 'carpentry',
      water: 'droplet',
      appliance: 'appliance',
      door: 'carpentry',
      electric: 'zap'
    }
    const metaParts = []
    if (rec.price != null && rec.price !== '') metaParts.push('起价 ¥' + rec.price)
    if (rec.duration != null && rec.duration !== '') metaParts.push('预计' + rec.duration + '分钟')
    return {
      id: rec.id || rec.key,
      name: rec.name || '推荐服务',
      meta: rec.meta || metaParts.join(' · ') || '价格与工期请以师傅报价为准',
      icon: buildIcon(iconMap[rec.key] || 'carpentry', COLORS.brand)
    }
  },

  // 推荐卡立即预约
  onBookRec(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({
      url: '/pages/client-publish/index?serviceId=' + id,
      fail: () => wx.showToast({ title: '暂未开放', icon: 'none' })
    })
  },

  // 麦克风按钮：调用语音输入
  onMicTap() {
    wx.showToast({ title: '语音输入开发中', icon: 'none' })
  },

  // 更多按钮
  onMore() {
    wx.showActionSheet({
      itemList: ['清空聊天记录', '联系人工客服'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.clearHistory()
        } else if (res.tapIndex === 1) {
          wx.showToast({ title: '正在转接人工客服', icon: 'none' })
        }
      }
    })
  },

  clearHistory() {
    wx.showModal({
      title: '清空聊天记录',
      content: '确定要清空所有聊天记录吗？',
      confirmColor: '#0D9488',
      success: (res) => {
        if (!res.confirm) return
        try {
          wx.removeStorageSync(CACHE_KEY)
        } catch (e) {}
        const welcome = [{
          id: 'm_' + Date.now(),
          role: 'service',
          content: '聊天记录已清空，有什么可以帮您？',
          time: this.fmtTime(Date.now())
        }]
        this.setData({ messages: welcome })
        this.saveHistory(welcome)
      }
    })
  },

  scrollBottom() {
    const list = this.data.messages
    if (!list.length) return
    this.setData({ scrollIntoView: 'msg-' + list[list.length - 1].id })
  },

  onBack() {
    wx.navigateBack({ delta: 1 })
  }
})

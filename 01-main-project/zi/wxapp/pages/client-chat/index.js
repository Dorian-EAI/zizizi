// pages/client-chat/index.js — AI 下单助手（文字 + 照片 -> 订单草稿 -> 确认下单）
const app = getApp()
const { buildIcon, COLORS } = require('../../utils/icons')

const CACHE_KEY = 'client_chat_history'
const SESSION_KEY = 'client_chat_session_id'
const MAX_PHOTOS = 3

const DEFAULT_QUICK = [
  '空调不制冷，明天上午来修',
  '厨房水管漏水，越快越好',
  '卫生间下水道堵了',
  '门锁坏了，今天下午能来吗'
]

const QUICK_SERVICES = [
  { key: 'electric', name: '水电维修' },
  { key: 'plumbing', name: '管道疏通' },
  { key: 'air_condition', name: '空调维修' },
  { key: 'door_window', name: '门窗维修' }
]

const WELCOME = {
  id: 'm_welcome',
  role: 'service',
  content: '你好，我是自家人的下单助手。直接说哪里坏了、什么时候方便，或者拍张照片给我，我来帮你安排师傅。',
  time: '',
  actions: [],
  options: { services: [], addresses: [], times: [] },
  draft: null,
  order: null,
  hasNavigate: false
}

Page({
  data: {
    statusBarHeight: 20,
    messages: [],
    inputValue: '',
    pendingImages: [],
    quickQuestions: DEFAULT_QUICK,
    quickServices: QUICK_SERVICES,
    chatTime: '',
    scrollIntoView: '',
    sending: false,
    sessionId: '',
    icons: {}
  },

  onLoad() {
    const now = new Date()
    const pad = (n) => (n < 10 ? '0' + n : '' + n)
    const chatTime = '今天 ' + pad(now.getHours()) + ':' + pad(now.getMinutes())
    let sessionId = ''
    try {
      sessionId = wx.getStorageSync(SESSION_KEY) || ''
    } catch (e) {}
    this.setData({
      statusBarHeight: app.globalData.statusBarHeight || 20,
      chatTime,
      sessionId,
      icons: {
        back: buildIcon('arrowLeft', COLORS.text1),
        bot: buildIcon('bot', COLORS.white),
        more: buildIcon('list', COLORS.text1),
        camera: buildIcon('camera', COLORS.brand),
        mic: buildIcon('phone', COLORS.brand),
        send: buildIcon('navigation', COLORS.white)
      }
    })
    this.loadHistory()
  },

  loadHistory() {
    try {
      const cached = wx.getStorageSync(CACHE_KEY)
      if (cached && cached.length) {
        const messages = cached.map(item => Object.assign({}, item, {
          actions: item.actions || [],
          options: Object.assign({ services: [], addresses: [], times: [] }, item.options || {}),
          draft: item.draft || null,
          order: item.order || null,
          hasNavigate: (item.actions || []).some(action => action.type === 'navigate')
        }))
        this.setData({ messages })
        this.scrollBottom()
        return
      }
    } catch (e) {}
    const welcome = Object.assign({}, WELCOME, { time: this.fmtTime(Date.now()) })
    this.setData({ messages: [welcome] })
    this.saveHistory([welcome])
  },

  saveHistory(messages) {
    const list = (messages || this.data.messages || []).slice(-40).map(item => {
      const copy = Object.assign({}, item)
      // 临时文件路径重启后失效，只保留照片数量用于占位展示。
      delete copy.localImages
      return copy
    })
    try {
      wx.setStorageSync(CACHE_KEY, list)
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
    if (this.data.sending) return
    const text = this.data.inputValue.trim()
    const images = this.data.pendingImages.slice()
    if (!text && !images.length) return
    this.setData({ inputValue: '', pendingImages: [] })
    await this.sendMessage(text, images)
  },

  async onQuickTap(e) {
    const text = e.currentTarget.dataset.text
    if (!text || this.data.sending) return
    await this.sendMessage(text)
  },

  async onQuickService(e) {
    const key = e.currentTarget.dataset.key
    const item = this.data.quickServices.find(s => s.key === key)
    if (!item || this.data.sending) return
    await this.sendMessage(item.name)
  },

  // ===== 照片 =====
  async onChooseImage() {
    if (this.data.sending) return
    const remain = MAX_PHOTOS - this.data.pendingImages.length
    if (remain <= 0) {
      wx.showToast({ title: '最多上传 ' + MAX_PHOTOS + ' 张照片', icon: 'none' })
      return
    }
    if (!wx.chooseMedia) {
      wx.showToast({ title: '当前微信版本不支持拍照', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: async (res) => {
        const files = res.tempFiles || []
        const paths = []
        for (const file of files) {
          const compressed = await this.compressImage(file.tempFilePath)
          paths.push(compressed)
        }
        this.setData({ pendingImages: this.data.pendingImages.concat(paths) })
      }
    })
  },

  compressImage(src) {
    return new Promise((resolve) => {
      if (!wx.compressImage) return resolve(src)
      wx.compressImage({
        src,
        quality: 70,
        success: (res) => resolve(res.tempFilePath || src),
        fail: () => resolve(src)
      })
    })
  },

  onRemovePending(e) {
    const index = Number(e.currentTarget.dataset.index)
    const images = this.data.pendingImages.slice()
    images.splice(index, 1)
    this.setData({ pendingImages: images })
  },

  onPreviewImage(e) {
    const src = e.currentTarget.dataset.src
    if (!src) return
    const msg = this.data.messages.find(item => item.id === e.currentTarget.dataset.msgid)
    const urls = (msg && msg.localImages && msg.localImages.length) ? msg.localImages : [src]
    wx.previewImage({ current: src, urls })
  },

  readFileBase64(filePath) {
    return new Promise((resolve, reject) => {
      wx.getFileSystemManager().readFile({
        filePath,
        encoding: 'base64',
        success: (res) => resolve(res.data),
        fail: reject
      })
    })
  },

  async readImagesBase64(paths) {
    if (!paths.length) return []
    const result = []
    for (const path of paths) {
      try {
        result.push(await this.readFileBase64(path))
      } catch (e) {
        console.warn('读取照片失败', e)
      }
    }
    return result
  },

  // ===== 对话 =====
  async sendMessage(text, images) {
    const value = String(text || '').trim()
    const photos = images || []
    if ((!value && !photos.length) || this.data.sending) return

    const userMsg = {
      id: 'm_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      role: 'user',
      content: value || '照片',
      time: this.fmtTime(Date.now()),
      localImages: photos,
      imageCount: photos.length,
      actions: [],
      options: { services: [], addresses: [], times: [] },
      draft: null,
      order: null
    }
    const messages = this.data.messages.concat([userMsg])
    this.setData({ messages, sending: true })
    this.scrollBottom()
    this.saveHistory(messages)

    try {
      const payload = { message: value }
      if (this.data.sessionId) payload.session_id = this.data.sessionId
      if (photos.length) {
        payload.image_base64_list = await this.readImagesBase64(photos)
        if (!payload.image_base64_list.length) delete payload.image_base64_list
      }
      const resp = await app.getApi().ai.agentTurn(payload)
      this.handleAgentResponse(resp)
    } catch (e) {
      console.error('AI 下单助手回复失败', e)
      this.appendServiceMessage((e && e.message) || '网络开小差了，请稍后重试。')
    }
  },

  handleAgentResponse(resp) {
    const reply = resp && (resp.reply || resp.message)
    if (!reply) {
      this.appendServiceMessage('助手没有返回内容，请稍后重试。')
      return
    }
    if (resp.session_id && resp.session_id !== this.data.sessionId) {
      this.setData({ sessionId: resp.session_id })
      try {
        wx.setStorageSync(SESSION_KEY, resp.session_id)
      } catch (e) {}
    }
    const serviceMsg = {
      id: 'a_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      role: 'service',
      content: reply,
      time: this.fmtTime(Date.now()),
      actions: resp.actions || [],
      options: Object.assign({ services: [], addresses: [], times: [] }, resp.options || {}),
      draft: resp.draft || null,
      order: resp.order || null,
      hasNavigate: (resp.actions || []).some(action => action.type === 'navigate')
    }
    const messages = this.data.messages.concat([serviceMsg])
    this.setData({ messages, sending: false })
    this.scrollBottom()
    this.saveHistory(messages)
    if (resp.order && wx.vibrateShort) {
      wx.vibrateShort({ type: 'light' })
    }
  },

  appendServiceMessage(text) {
    const msg = {
      id: 'a_' + Date.now() + '_e',
      role: 'service',
      content: text,
      time: this.fmtTime(Date.now()),
      actions: [],
      options: { services: [], addresses: [], times: [] },
      draft: null,
      order: null,
      hasNavigate: false
    }
    const messages = this.data.messages.concat([msg])
    this.setData({ messages, sending: false })
    this.scrollBottom()
    this.saveHistory(messages)
  },

  async confirmOrder(token) {
    if (this.data.sending) return
    if (!token) {
      wx.showToast({ title: '确认信息已失效，请重新描述需求', icon: 'none' })
      return
    }
    await this.sendAction('confirm', token, '确认下单')
  },

  async cancelDraft() {
    if (this.data.sending) return
    await this.sendAction('cancel', '', '先不下单')
  },

  async sendAction(action, token, label) {
    const userMsg = {
      id: 'm_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
      role: 'user',
      content: label,
      time: this.fmtTime(Date.now()),
      localImages: [],
      imageCount: 0,
      actions: [],
      options: { services: [], addresses: [], times: [] },
      draft: null,
      order: null
    }
    const messages = this.data.messages.concat([userMsg])
    this.setData({ messages, sending: true })
    this.scrollBottom()
    this.saveHistory(messages)

    try {
      const payload = { action }
      if (this.data.sessionId) payload.session_id = this.data.sessionId
      if (token) payload.confirm_token = token
      const resp = await app.getApi().ai.agentTurn(payload)
      this.handleAgentResponse(resp)
    } catch (e) {
      this.appendServiceMessage((e && e.message) || '提交失败，请稍后重试。')
    }
  },

  onActionTap(e) {
    const dataset = e.currentTarget.dataset
    const msg = this.data.messages.find(item => item.id === dataset.msgid)
    const action = msg && msg.actions ? msg.actions[dataset.index] : null
    if (!action) return
    if (action.type === 'confirm_order') {
      this.confirmOrder(action.token)
    } else if (action.type === 'cancel_order_draft') {
      this.cancelDraft()
    } else if (action.type === 'navigate') {
      this.navigateTo(action.url)
    } else if (action.type === 'set_time' || action.type === 'set_service') {
      this.sendMessage(action.value || action.text)
    }
  },

  onOptionTap(e) {
    const dataset = e.currentTarget.dataset
    const msg = this.data.messages.find(item => item.id === dataset.msgid)
    if (!msg || this.data.sending) return
    if (dataset.kind === 'address') {
      const list = (msg.options && msg.options.addresses) || []
      const address = list[dataset.index]
      if (address) this.sendMessage('上门地址：' + address.text)
      return
    }
    if (dataset.kind === 'time') {
      const list = (msg.options && msg.options.times) || []
      const option = list[dataset.index]
      if (option) this.sendMessage(option.value || option.text)
      return
    }
    if (dataset.kind === 'service') {
      const list = (msg.options && msg.options.services) || []
      const option = list[dataset.index]
      if (option) this.sendMessage(option.text)
    }
  },

  navigateTo(url) {
    if (!url) return
    wx.navigateTo({
      url,
      fail: () => wx.showToast({ title: '页面暂不可用', icon: 'none' })
    })
  },

  // 麦克风按钮：语音输入后续接入
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

  async clearHistory() {
    wx.showModal({
      title: '清空聊天记录',
      content: '确定要清空所有聊天记录吗？',
      confirmColor: '#0D9488',
      success: async (res) => {
        if (!res.confirm) return
        try {
          if (this.data.sessionId) {
            await app.getApi().ai.agentTurn({
              session_id: this.data.sessionId,
              action: 'reset'
            })
          }
        } catch (e) {
          console.warn('重置会话失败', e)
        }
        try {
          wx.removeStorageSync(CACHE_KEY)
          wx.removeStorageSync(SESSION_KEY)
        } catch (e) {}
        const welcome = Object.assign({}, WELCOME, { time: this.fmtTime(Date.now()) })
        this.setData({
          messages: [welcome],
          sessionId: '',
          pendingImages: []
        })
        this.saveHistory([welcome])
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
